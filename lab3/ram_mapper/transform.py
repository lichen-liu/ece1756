from abc import ABC, abstractmethod
from collections import Counter, defaultdict
import copy
from enum import IntEnum, auto
from itertools import starmap
import math
import random
from typing import Callable, DefaultDict, Dict, Iterable, Iterator, List, NamedTuple, Set, Tuple


from .siv_heuristics import calculate_chip_leftover_ram_supply, calculate_fpga_qor, calculate_fpga_qor_for_ram_config, calculate_ram_area

from .logger import logger
from .logical_ram import LogicalRam, RamMode, RamShape, RamShapeFit
from .utils import list_add, list_sub, sorted_dict_items, proccess_initializer
from .mapping_config import AllCircuitConfig, CircuitConfig, CombinedLogicalRamConfig, LogicalRamConfig, PhysicalRamConfig, RamConfig, RamSplitDimension
from .logical_circuit import LogicalCircuit
from .siv_arch import RegularLogicBlockArch, SIVArch, SIVRamArch, determine_extra_luts
from multiprocessing import Pool


def solve_all_circuits(archs: SIVArch, logical_circuits: Dict[int, LogicalCircuit], args) -> AllCircuitConfig:
    num_circuits = len(logical_circuits)
    logger.warning(
        f'Solving for {num_circuits} circuits using {args.processes} processes')

    acc = AllCircuitConfig()

    def starmap_dispatcher(starmap_func):
        circuit_configs = starmap_func(solve_single_circuit, map(
            lambda lc: (archs, lc, num_circuits), logical_circuits.values()))
        for circuit_config in circuit_configs:
            acc.insert_circuit_config(cc=circuit_config)

    if args.processes == 1:
        starmap_dispatcher(starmap_func=starmap)
    else:
        with Pool(processes=args.processes, initializer=proccess_initializer, initargs=(args,)) as p:
            starmap_dispatcher(starmap_func=p.starmap)
    return acc


def solve_single_circuit(archs: SIVArch, logical_circuit: LogicalCircuit, num_circuits: int) -> CircuitConfig:
    should_continue = True

    prc_candidates = generate_candidate_prc_for_lcs(
        archs=archs, logical_rams=logical_circuit.rams.values())
    # Generate an initial config
    solver = SingleLevelCircuitInitialSolution(
        archs=archs,
        logical_circuit=logical_circuit,
        prc_candidates=prc_candidates)
    solver.solve()
    circuit_config = solver.circuit_config()
    physical_ram_uid = solver.assign_physical_ram_uid()

    # Incrementally improving
    solver = CandidateBasedCircuitOptimizer(
        archs=archs,
        logical_circuit=logical_circuit,
        circuit_config=circuit_config,
        seed=circuit_config.circuit_id,
        physical_ram_uid=physical_ram_uid,
        prc_candidates=prc_candidates,
        name='L1')
    solver.solve()
    circuit_config = solver.circuit_config()
    physical_ram_uid = solver.assign_physical_ram_uid()

    if should_continue and True:
        # Split RAM
        solver = SingleLevelSplitRamCircuitOptimizer(
            archs=archs,
            logical_circuit=logical_circuit,
            circuit_config=circuit_config,
            physical_ram_uid=physical_ram_uid,
        )
        rc_split_width_list, _ = solver.solve()
        circuit_config = solver.circuit_config()
        physical_ram_uid = solver.assign_physical_ram_uid()

        if len(rc_split_width_list) > 0:
            # Incrementally improving
            def merge_dict(dd, to_merge):
                for k, v in to_merge.items():
                    dd[k].extend(v)
            prc_candidates = defaultdict(list)
            merge_dict(prc_candidates,
                       generate_candidate_prc_for_rcs(
                           archs=archs,
                           ram_configs=rc_split_width_list,
                           locator=TwoLevelRightPRCLocator()))
            merge_dict(prc_candidates,
                       generate_candidate_prc_for_rcs(
                           archs=archs,
                           ram_configs=rc_split_width_list,
                           locator=TwoLevelLeftPRCLocator()))
            splitted_ram_ids = set(rc.ram_id for rc in rc_split_width_list)
            merge_dict(prc_candidates,
                       generate_candidate_prc_for_rcs(
                           archs=archs,
                           ram_configs=filter(
                               lambda rc: rc.ram_id not in splitted_ram_ids, circuit_config.rams.values()),
                           locator=SingleLevelPRCLocator()))
            solver = CandidateBasedCircuitOptimizer(
                archs=archs,
                logical_circuit=logical_circuit,
                circuit_config=circuit_config,
                seed=circuit_config.circuit_id + num_circuits,
                physical_ram_uid=physical_ram_uid,
                prc_candidates=prc_candidates,
                name='L2',
                enable_save_best=True)
            solver.solve(effort_factor=1.0)
            circuit_config = solver.circuit_config()
            physical_ram_uid = solver.assign_physical_ram_uid()

    if should_continue and True:
        # Share physical ram
        solver = SharingCircuitOptimizer(
            archs=archs,
            logical_circuit=logical_circuit,
            circuit_config=circuit_config,
            physical_ram_uid=physical_ram_uid)
        solver.solve()
        circuit_config = solver.circuit_config()
        # physical_ram_uid = solver.assign_physical_ram_uid()

    return circuit_config


def legal_ram_shape_fit_filter(fit: RamShapeFit) -> bool:
    return fit.num_series <= 16


def get_ram_shape_fits(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape) -> Iterator[Tuple[RamShape, RamShapeFit]]:
    return ((physical_shape, fit)
            for physical_shape in candidate_physical_shapes if legal_ram_shape_fit_filter(fit := target_logical_shape.get_fit(smaller_shape=physical_shape)))


class PRCLocator(ABC):
    @abstractmethod
    def get_lrc_from_rc(self, rc: RamConfig) -> LogicalRamConfig:
        pass

    def get_prc_from_rc(self, rc: RamConfig) -> PhysicalRamConfig:
        return self.get_lrc_from_rc(rc).prc

    def set_prc_to_rc(self, rc: RamConfig, prc: PhysicalRamConfig):
        self.get_lrc_from_rc(rc).prc = prc


class PRCCandidate(NamedTuple):
    prc: PhysicalRamConfig
    locator: PRCLocator


class SingleLevelPRCLocator(PRCLocator):
    def get_lrc_from_rc(self, rc: RamConfig) -> LogicalRamConfig:
        return rc.lrc


class TwoLevelRightPRCLocator(PRCLocator):
    def get_lrc_from_rc(self, rc: RamConfig) -> LogicalRamConfig:
        return rc.lrc.clrc.lrc_r


class TwoLevelLeftPRCLocator(PRCLocator):
    def get_lrc_from_rc(self, rc: RamConfig) -> LogicalRamConfig:
        return rc.lrc.clrc.lrc_l


def generate_candidate_prc_for_logical_shape(archs: SIVArch, logical_shape: RamShape, ram_mode: RamMode, locator: PRCLocator) -> List[PRCCandidate]:
    # Convert candidates into LogicalRamConfigs
    def convert_to_prc(ram_arch_id: int, physical_ram_shape: RamShape, physical_ram_shape_fit: RamShapeFit) -> PRCCandidate:
        prc = PhysicalRamConfig(
            id=-1,
            physical_shape_fit=physical_ram_shape_fit,
            ram_arch_id=ram_arch_id,
            ram_mode=ram_mode,
            physical_shape=physical_ram_shape)
        return PRCCandidate(prc=prc, locator=locator)

    # Find candidates
    candidate_prc_list = list()
    for ram_arch in archs.ram_archs.values():
        if ram_mode not in ram_arch.get_supported_mode():
            continue
        physical_shapes = ram_arch.get_shapes_for_mode(ram_mode)
        candidate_physical_shape_fits = get_ram_shape_fits(
            candidate_physical_shapes=physical_shapes, target_logical_shape=logical_shape)
        candidate_prc_list.extend(
            map(lambda psf: convert_to_prc(ram_arch_id=ram_arch.get_id(), physical_ram_shape=psf[0], physical_ram_shape_fit=psf[1]), candidate_physical_shape_fits))

    return candidate_prc_list


def generate_candidate_prc_for_lcs(archs: SIVArch, logical_rams: Iterable[LogicalRam]) -> Dict[int, List[PRCCandidate]]:
    locator = SingleLevelPRCLocator()
    return {logical_ram.ram_id:
            generate_candidate_prc_for_logical_shape(
                archs=archs, logical_shape=logical_ram.shape, ram_mode=logical_ram.mode, locator=locator)
            for logical_ram in logical_rams}


def generate_candidate_prc_for_rcs(archs: SIVArch, ram_configs: Iterable[RamConfig], locator: PRCLocator) -> Dict[int, List[PRCCandidate]]:
    return {ram_config.ram_id:
            generate_candidate_prc_for_logical_shape(
                archs=archs, logical_shape=locator.get_lrc_from_rc(ram_config).logical_shape, ram_mode=ram_config.ram_mode, locator=locator)
            for ram_config in ram_configs}


class CircuitSolverBase:
    def __init__(self, archs: SIVArch, logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, physical_ram_uid: int, name: str):
        self._archs = archs
        self._logical_circuit = logical_circuit
        self._physical_ram_uid = physical_ram_uid
        self._circuit_config = circuit_config
        self._name = name

    def circuit_config(self) -> CircuitConfig:
        return self._circuit_config

    def logical_circuit(self) -> LogicalCircuit:
        return self._logical_circuit

    def archs(self) -> SIVArch:
        return self._archs

    def ram_arch(self, ram_arch_id: int) -> SIVRamArch:
        return self._archs.ram_archs[ram_arch_id]

    def lb_arch(self) -> RegularLogicBlockArch:
        return self._archs.lb_arch

    def assign_physical_ram_uid(self) -> int:
        assigned_value = self._physical_ram_uid
        self._physical_ram_uid += 1
        return assigned_value

    def msg_header(self) -> str:
        return f'C{self.logical_circuit().circuit_id} {self._name}'


class SingleLevelSplitRamCircuitOptimizer(CircuitSolverBase):
    def __init__(self, archs: SIVArch, logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, physical_ram_uid: int):
        super().__init__(archs=archs,
                         logical_circuit=logical_circuit,
                         circuit_config=circuit_config,
                         physical_ram_uid=physical_ram_uid,
                         name='CLIFF SPLIT')
        # TODO: 3
        self._cliff_max_num_parallel = 2

    def split_rc_by_width(self, rc: RamConfig, cliff_num_parallel: int):
        '''
        Split the RC by width using the same physical config except for num_parallel=1,
        will have no impact on area, thus using it as initial solution
        '''
        old_prc = rc.lrc.prc
        old_prc_fit = old_prc.physical_shape_fit
        assert cliff_num_parallel > 0
        assert old_prc_fit.num_parallel >= cliff_num_parallel+1
        old_logical_shape = rc.lrc.logical_shape

        l_prc_fit = RamShapeFit(
            num_series=old_prc_fit.num_series,
            num_parallel=old_prc_fit.num_parallel-cliff_num_parallel)
        l_prc = PhysicalRamConfig(
            id=old_prc.id,
            physical_shape_fit=l_prc_fit,
            ram_arch_id=old_prc.ram_arch_id,
            ram_mode=old_prc.ram_mode,
            physical_shape=old_prc.physical_shape)
        l_logical_shape = RamShape(
            width=l_prc_fit.num_parallel*l_prc.physical_shape.width,
            depth=old_logical_shape.depth)
        l_lrc = LogicalRamConfig(logical_shape=l_logical_shape, prc=l_prc)

        # Splitted Cliff, as lrc_r
        r_prc_fit = RamShapeFit(
            num_series=old_prc_fit.num_series,
            num_parallel=cliff_num_parallel)
        r_prc = PhysicalRamConfig(
            id=self.assign_physical_ram_uid(),
            physical_shape_fit=r_prc_fit,
            ram_arch_id=old_prc.ram_arch_id,
            ram_mode=old_prc.ram_mode,
            physical_shape=old_prc.physical_shape)
        r_logical_shape = RamShape(
            width=old_logical_shape.width-l_logical_shape.width,
            depth=old_logical_shape.depth)
        r_lrc = LogicalRamConfig(logical_shape=r_logical_shape, prc=r_prc)

        clrc = CombinedLogicalRamConfig(
            split=RamSplitDimension.parallel,
            lrc_l=l_lrc,
            lrc_r=r_lrc)
        lrc = LogicalRamConfig(logical_shape=old_logical_shape, clrc=clrc)

        # Install
        # assert rc.lrc.get_extra_lut_count() == lrc.get_extra_lut_count()
        # assert rc.lrc.get_physical_ram_count() == lrc.get_physical_ram_count()
        rc.lrc = lrc

    def solve(self) -> Tuple[List[RamConfig], List[RamConfig]]:
        '''
        (rc_split_width_list, rc_split_depth_list)
        '''
        rc_split_width_list, rc_split_depth_list = self.split_cliff()
        logger.warning(
            f'{self.msg_header()}: Split {len(rc_split_width_list)} RAMs in width dimension (parallel)')
        return (rc_split_width_list, rc_split_depth_list)

    def split_cliff(self,  verbose: bool = False) -> Tuple[List[RamConfig], List[RamConfig]]:
        '''
        (split_width_list, split_depth_list)
        '''
        split_width_list = list()
        split_depth_list = list()
        for ram_id, rc in sorted_dict_items(self.circuit_config().rams):
            prc = rc.lrc.prc
            if prc.physical_shape_fit.get_count() == 1:
                continue
            total_physical_shape = prc.get_shape()
            logical_shape = rc.lrc.logical_shape
            wasted_bits = total_physical_shape.get_size() - logical_shape.get_size()

            extra_width = total_physical_shape.width - logical_shape.width
            extra_depth = total_physical_shape.depth - logical_shape.depth

            can_reduce_width = extra_width > 0 and prc.physical_shape_fit.num_parallel > 1
            can_reduce_depth = extra_depth > 0 and prc.physical_shape_fit.num_series > 1
            if not (can_reduce_width or can_reduce_depth):
                continue

            if verbose:
                logger.info(
                    f'{self.msg_header()}: RAM {ram_id} {rc.serialize(0)}')
                logger.info(f'{self.msg_header()}:    physical:{prc.physical_shape} ' +
                            f'total_physical:{total_physical_shape}, ' +
                            f'logical:{logical_shape}, ' +
                            f'wasted:{wasted_bits}, ' +
                            f'extra_width:{extra_width}, extra_depth:{extra_depth}')
                logger.info(
                    f'{self.msg_header()}:    can_reduce_width={can_reduce_width}, can_reduce_depth={can_reduce_depth}')

            if can_reduce_width:
                if verbose:
                    logger.info(
                        f'{self.msg_header()}:    Should split width')
                split_width_list.append(rc)
                # self.split_rc_by_width(rc=rc, cliff_num_parallel=max(
                #     min(prc.physical_shape_fit.num_parallel//2, self._cliff_max_num_parallel), 1))
                self.split_rc_by_width(
                    rc, min(self._cliff_max_num_parallel, prc.physical_shape_fit.num_parallel-1))
            else:
                if verbose:
                    logger.info(
                        f'{self.msg_header()}:    Should split depth')
                split_depth_list.append(rc)

        return (split_width_list, split_depth_list)


class TemperatureScheduleParam(NamedTuple):
    num_steps: int
    current_step: int
    num_accepted: int

    def current_step_fraction(self) -> float:
        return (self.current_step + 1) / self.num_steps

    def acceptance_ratio(self) -> float:
        return 0 if self.current_step == 0 else self.num_accepted/self.current_step


class MoveOutcome(IntEnum):
    ACCEPTED_AREA = auto()
    ACCEPTED_LOCAL_AREA = auto()
    ACCEPTED_TEMPERATURE = auto()
    REJECTED_AREA = auto()
    ABORT_DUPLICATED = auto()

    def is_accepted(self) -> bool:
        return self < self.REJECTED_AREA


def area_str(initial_area: int, final_area: int, best_area: int) -> str:
    delta_to_initial = final_area-initial_area
    delta_to_best = final_area-best_area
    return f'final_area={final_area} (delta_initial={delta_to_initial} delta_best={delta_to_best})'


class CandidateBasedCircuitOptimizer(CircuitSolverBase):
    '''
    Only perform moves for ram_id defined in prc_candidates, the relationship between rc -> prc must be provided by prc_candidates
    '''

    def __init__(self,
                 archs: SIVArch,
                 logical_circuit: LogicalCircuit,
                 circuit_config: CircuitConfig,
                 seed: int,
                 physical_ram_uid: int,
                 prc_candidates: Dict[int, List[PRCCandidate]],
                 name: str,
                 allow_early_exit: bool = True,
                 enable_save_best: bool = False):
        super().__init__(archs=archs,
                         logical_circuit=logical_circuit,
                         circuit_config=circuit_config,
                         physical_ram_uid=physical_ram_uid,
                         name=name)
        # RNG
        self._rng = random.Random(seed)

        # Search space
        self._prc_candidates = prc_candidates
        self._prc_candidates_ram_ids = list(prc_candidates.keys())
        self._candidate_prc_size = sum(
            map(lambda prc_list: len(prc_list), prc_candidates.values()))

        # Area calculation
        self.prepare_area_calculation_cache()
        # Save the best copy
        self._enable_save_best = enable_save_best
        self._best_fpga_area_saved = self._fpga_area
        if self._enable_save_best:
            self._best_circuit_config_saved = copy.deepcopy(
                self.circuit_config())

        self._allow_early_exit = allow_early_exit

        self._zero_delta_fpga_area_counter = 0

    def get_prc_candidate(self, logical_ram_id: int) -> List[PRCCandidate]:
        return self._prc_candidates[logical_ram_id]

    def prepare_area_calculation_cache(self):
        self._extra_lut_count = self.circuit_config().get_extra_lut_count()
        self._physical_ram_count = self.circuit_config().get_physical_ram_count()
        self._fpga_area = self.calculate_tiles_fast(
            extra_lut_count=self._extra_lut_count, physical_ram_count=self._physical_ram_count)
        self._leftover_ram_supply_count = calculate_chip_leftover_ram_supply(
            archs=self.archs(), tile_count=self._fpga_area, block_usage=self._physical_ram_count)

    def switch_to_best_circuit_config(self):
        assert self._enable_save_best
        if self._best_fpga_area_saved < self._fpga_area:
            self._circuit_config = self._best_circuit_config_saved
            logger.info(
                f'{self.msg_header()}: switch to best area config: {self._fpga_area} -> {self._best_fpga_area_saved}')
            self.prepare_area_calculation_cache()

    def is_global_optimum(self) -> bool:
        # Already achieved best possible FPGA area (i.e., the area that regular LBs from logical circuits need),
        # no point in continuing
        return self._allow_early_exit and self._fpga_area <= self.logical_circuit().num_logic_blocks

    def get_search_space_size(self) -> int:
        return self._candidate_prc_size

    def select_rc_to_move(self) -> RamConfig:
        return self.circuit_config().rams[self._rng.choice(self._prc_candidates_ram_ids)]

    def propose_move(self, rc: RamConfig, is_targeted: bool) -> PRCCandidate:
        if is_targeted:
            # 40% probability
            if self._rng.uniform(0, 1) < 0.4:
                for target_ramarch_id, _ in sorted(enumerate(self._leftover_ram_supply_count), key=lambda kv: kv[1], reverse=True):
                    candidates = list(filter(lambda candidate: candidate.prc.ram_arch_id ==
                                             target_ramarch_id, self.get_prc_candidate(logical_ram_id=rc.ram_id)))
                    if len(candidates) > 0:
                        return self._rng.choice(candidates)

        # Randomly pick a new prc
        return self._rng.choice(
            self.get_prc_candidate(logical_ram_id=rc.ram_id))

    def evaluate_apply_move(self, rc: RamConfig, prc_candidate: PRCCandidate, should_accept_worse_func: Callable[[int, int], bool]) -> MoveOutcome:
        '''
        should_accept_worse_func(new_area,old_area)
        Return True if new prc is accepted; otherwise False
        '''
        prc_new = prc_candidate.prc
        prc_new_locator = prc_candidate.locator

        # Save old
        prc_old = prc_new_locator.get_prc_from_rc(rc=rc)
        # Get old area
        area_old = self._fpga_area

        if prc_old == prc_new:
            return MoveOutcome.ABORT_DUPLICATED

        # Calculate new area
        def extra_luts(prc: PhysicalRamConfig) -> int:
            return determine_extra_luts(num_series=prc.physical_shape_fit.num_series, logical_w=rc.lrc.logical_shape.width, ram_mode=rc.ram_mode)
        prc_old_extra_luts = extra_luts(prc_old)
        prc_new_extra_luts = extra_luts(prc_new)
        new_extra_lut_count = self._extra_lut_count - \
            prc_old_extra_luts + prc_new_extra_luts
        new_physical_ram_count = list_add(list_sub(self._physical_ram_count,
                                                   prc_old.get_physical_ram_count()),  prc_new.get_physical_ram_count())
        area_new = self.calculate_tiles_fast(
            extra_lut_count=new_extra_lut_count, physical_ram_count=new_physical_ram_count)

        def apply_move():
            # Install new
            prc_new.id = prc_old.id
            prc_new_locator.set_prc_to_rc(rc=rc, prc=prc_new)
            # Update area
            self._extra_lut_count = new_extra_lut_count
            self._physical_ram_count = new_physical_ram_count
            self._fpga_area = area_new
            self._leftover_ram_supply_count = calculate_chip_leftover_ram_supply(
                archs=self.archs(), tile_count=self._fpga_area, block_usage=self._physical_ram_count)
            # Save the best circuit config
            if self._fpga_area < self._best_fpga_area_saved:
                self._best_fpga_area_saved = self._fpga_area
                if self._enable_save_best:
                    self._best_circuit_config_saved = copy.deepcopy(
                        self.circuit_config())

        # If new is better than old, apply the change
        if area_new < area_old:
            apply_move()
            return MoveOutcome.ACCEPTED_AREA

        if area_new == area_old:
            self._zero_delta_fpga_area_counter += 1
            local_area_old = calculate_ram_area(
                archs=self.archs(),
                extra_lut_count=prc_old_extra_luts,
                prc=prc_old)
            local_area_new = calculate_ram_area(
                archs=self.archs(),
                extra_lut_count=prc_new_extra_luts,
                prc=prc_new)
            if local_area_new < local_area_old:
                apply_move()
                return MoveOutcome.ACCEPTED_LOCAL_AREA

        if should_accept_worse_func(area_new, area_old):
            apply_move()
            return MoveOutcome.ACCEPTED_TEMPERATURE

        return MoveOutcome.REJECTED_AREA

    def try_random_single_prc_move(self, should_accept_worse_func: Callable[[int, int], bool]) -> MoveOutcome:
        '''
        should_accept_worse_func(new_area,old_area)
        Return True if new prc is accepted; otherwise False
        '''
        rc = self.select_rc_to_move()

        # Randomly pick a new prc
        prc_candidate = self.propose_move(rc=rc, is_targeted=True)

        return self.evaluate_apply_move(rc=rc, prc_candidate=prc_candidate, should_accept_worse_func=should_accept_worse_func)

    def calculate_tiles_fast(self, extra_lut_count: int, physical_ram_count: List[int]) -> int:
        return calculate_fpga_qor(
            archs=self.archs(),
            logic_block_count=self.logical_circuit().num_logic_blocks,
            extra_lut_count=extra_lut_count,
            physical_ram_count=physical_ram_count,
            skip_area=True).required_logic_block_count

    def solve(self, effort_factor: float = 1.0):
        # Hillclimb
        # -------param-------
        exploration_factor = max(1, int(20 * effort_factor))
        max_outer_loop = max(1, int(20 * effort_factor))
        initial_temperature = 50 * effort_factor
        target_acceptance_ratio = 0.1
        # quench_starting_step_fraction = 0.95
        quench_starting_step_fraction = 2  # Disable
        # -------param-------
        search_space_size = self.get_search_space_size()
        num_steps = search_space_size * exploration_factor

        logger.info(
            f'{self.msg_header()} ANNEAL: {num_steps} steps ({exploration_factor} * {search_space_size}), starting at temperature {initial_temperature}')

        def temperature_schedule(param: TemperatureScheduleParam) -> float:
            step_fraction = param.current_step_fraction()
            current_step = param.current_step
            if step_fraction >= quench_starting_step_fraction:
                return 0
            else:
                return initial_temperature / (current_step + 1)

        self.anneal(num_steps=num_steps,
                    target_acceptance_ratio=target_acceptance_ratio,
                    max_outer_loop=max_outer_loop,
                    temperature_schedule=temperature_schedule,
                    stats=False)

        if self._enable_save_best:
            self.switch_to_best_circuit_config()

        self.greedy()

    def anneal(self, num_steps: int, target_acceptance_ratio: float, max_outer_loop: int, temperature_schedule: Callable[[TemperatureScheduleParam], float], stats: bool = False):
        assert num_steps > 0
        outcome_stats = Counter()
        num_accepted = 0
        steps_performed = 0
        total_steps_to_perform = 0

        start_area = self._fpga_area
        do_early_exit = False
        for _ in range(max_outer_loop):
            total_steps_to_perform += num_steps
            for _ in range(num_steps):
                # Only executes when needed
                def should_accept_worse(new_area: int, old_area: int) -> bool:
                    # Only computed when needed, temperature_schedule must not be dependening on previous states
                    temperature = temperature_schedule(
                        TemperatureScheduleParam(num_steps=total_steps_to_perform, current_step=steps_performed, num_accepted=num_accepted))
                    return temperature > 0 and self._rng.uniform(0, 1) < math.exp(-((new_area - old_area)/old_area)/temperature)

                outcome = self.try_random_single_prc_move(should_accept_worse)

                # Book-keeping
                if outcome.is_accepted():
                    num_accepted += 1
                if stats:
                    outcome_stats[outcome] += 1
                steps_performed += 1

                if self.is_global_optimum():
                    do_early_exit = True
                    break

            if do_early_exit:
                break

            current_acceptance_ratio = num_accepted/steps_performed
            if current_acceptance_ratio > target_acceptance_ratio:
                logger.info(
                    f'{self.msg_header()} ANNEAL: ' +
                    f'extended {num_steps} steps ({steps_performed} / {total_steps_to_perform+num_steps}) ' +
                    f'b/c acceptance ratio {current_acceptance_ratio} > target {target_acceptance_ratio} ' +
                    f'at temperature {temperature_schedule(TemperatureScheduleParam(num_steps=total_steps_to_perform+num_steps, current_step=steps_performed, num_accepted=num_accepted))}')
            else:
                break
        area_stats = area_str(
            initial_area=start_area, final_area=self._fpga_area, best_area=self._best_fpga_area_saved)
        logger.warning(
            f'{self.msg_header()} ANNEAL: ' +
            f'{steps_performed} done (was {num_steps}), {num_accepted} accepted ({num_accepted/steps_performed*100:.2f}%), {self._zero_delta_fpga_area_counter} zero fpga-area deltas, ' +
            f'early_exited={do_early_exit}. ' +
            f'{area_stats}')
        if stats:
            logger.info(f'    Stats {str(outcome_stats)}')

    def greedy(self):
        is_converged = False
        convergence_loop_counter = 0
        num_accepted = 0
        is_early_exited = False
        start_area = self._fpga_area
        while not is_converged:
            is_converged = True
            for logical_ram_id, prc_new_list in self._prc_candidates.items():
                rc = self.circuit_config().rams[logical_ram_id]
                for prc_new in prc_new_list:
                    outcome = self.evaluate_apply_move(
                        rc=rc, prc_candidate=prc_new, should_accept_worse_func=lambda _a, _b: False)
                    if outcome.is_accepted():
                        is_converged = False
                        num_accepted += 1
            convergence_loop_counter += 1
            if self.is_global_optimum():
                is_converged = True
                is_early_exited = True

        search_space_size = self.get_search_space_size()
        steps_performed = convergence_loop_counter * search_space_size
        area_stats = area_str(
            initial_area=start_area, final_area=self._fpga_area, best_area=self._best_fpga_area_saved)
        logger.warning(
            f'{self.msg_header()} GREEDY: ' +
            f'{convergence_loop_counter}*{search_space_size}, {steps_performed} done, {num_accepted} accepted ({num_accepted/steps_performed*100:.2f}%), ' +
            f'early_exited={is_early_exited}. ' +
            f'{area_stats}')


class SingleLevelCircuitInitialSolution(CircuitSolverBase):
    def __init__(self, archs: SIVArch, logical_circuit: LogicalCircuit, prc_candidates: Dict[int, List[PRCCandidate]]):
        super().__init__(archs=archs,
                         logical_circuit=logical_circuit,
                         circuit_config=CircuitConfig(
                             circuit_id=logical_circuit.circuit_id),
                         name='INITIAL',
                         physical_ram_uid=0)
        # Search space
        self._prc_candidates = prc_candidates

    def get_prc_candidate(self, logical_ram_id: int) -> List[PRCCandidate]:
        return self._prc_candidates[logical_ram_id]

    def solve_single_ram(self, logical_ram: LogicalRam) -> RamConfig:
        candidate_lrc_list = map(lambda prc_candidate: LogicalRamConfig(
            logical_shape=logical_ram.shape, prc=prc_candidate.prc), self.get_prc_candidate(logical_ram_id=logical_ram.ram_id))

        def area_estimator(lrc: LogicalRamConfig) -> int:
            return calculate_fpga_qor_for_ram_config(archs=self.archs(), logic_block_count=0, logical_ram_config=lrc, ram_mode=logical_ram.mode, skip_area=True).fpga_area
        best_candidate_lrc = min(map(lambda lrc: (lrc, area_estimator(
            lrc)), candidate_lrc_list), key=lambda p: p[1])[0]
        # Finalize the best candidate
        best_candidate_lrc.prc.id = self.assign_physical_ram_uid()
        return RamConfig(circuit_id=logical_ram.circuit_id, ram_id=logical_ram.ram_id, ram_mode=logical_ram.mode, lrc=best_candidate_lrc)

    def solve(self):
        self.circuit_config().rams.clear()
        for lr in self.logical_circuit().rams.values():
            self.circuit_config().insert_ram_config(self.solve_single_ram(logical_ram=lr))


class SharingCircuitOptimizer(CircuitSolverBase):
    def __init__(self, archs: SIVArch, logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, physical_ram_uid: int):
        super().__init__(archs=archs,
                         logical_circuit=logical_circuit,
                         circuit_config=circuit_config,
                         physical_ram_uid=physical_ram_uid,
                         name='SHARING')

    def find_single_port_lrcs(self) -> Dict[int, LogicalRamConfig]:
        single_port_lrc_dict: Dict[int, LogicalRamConfig] = dict()

        def find_single_port_lrc(lrc: LogicalRamConfig):
            if lrc.prc.ram_mode.num_ports() == 1:
                single_port_lrc_dict[lrc.prc.id] = lrc
        self.circuit_config().execute_on_leaf(find_single_port_lrc)

        return single_port_lrc_dict

    def find_provider_lrcs(self, single_port_lrc_dict: Dict[int, LogicalRamConfig]) -> List[LogicalRamConfig]:
        # All possible provider lrc
        def can_be_provider(lrc: LogicalRamConfig):
            if lrc.prc.get_shape().depth > lrc.logical_shape.depth:
                ram_arch = self.ram_arch(lrc.prc.ram_arch_id)
                if RamMode.TrueDualPort in ram_arch.get_supported_mode():
                    if lrc.prc.physical_shape in ram_arch.get_shapes_for_mode(RamMode.TrueDualPort):
                        return True
            return False

        return list(
            filter(can_be_provider, single_port_lrc_dict.values()))

    def find_sharing_pairs(self, single_port_lrc_dict: Dict[int, LogicalRamConfig], lrc_provider_list: List[LogicalRamConfig]) -> List[Tuple[float, int, int]]:
        provider_id_set = set(lrc.prc.id for lrc in lrc_provider_list)
        # Find possible pairs
        # (saved_area_per_bits, p_id, r_id)
        sharing_pairs: List[Tuple[float, int, int]] = list()
        for provider_lrc in lrc_provider_list:
            p_shape = provider_lrc.logical_shape
            p_physical_shape = provider_lrc.prc.physical_shape
            p_total_physical_shape = provider_lrc.prc.get_shape()
            p_id = provider_lrc.prc.id
            for receiver_lrc in single_port_lrc_dict.values():
                r_id = receiver_lrc.prc.id
                if p_id == r_id:
                    continue

                r_shape = receiver_lrc.logical_shape

                # The aggregate depth of RAM 0 and 1 cannot be greater than the physical RAM???s
                if p_shape.depth + r_shape.depth > p_physical_shape.depth:
                    continue
                # Physical RAM???s width must be equal or greater than RAM 0???s width and RAM 1???s width.
                if r_shape.width > p_physical_shape.width:
                    continue

                provider_free_bits = p_total_physical_shape.get_size() - p_shape.get_size()
                if r_id in provider_id_set:
                    r_total_physical_shape = receiver_lrc.prc.get_shape()
                    provider_free_bits += r_total_physical_shape.get_size() - r_shape.get_size()

                r_logical_ram_mode = receiver_lrc.prc.ram_mode

                new_receiver_lrc = LogicalRamConfig(
                    logical_shape=receiver_lrc.logical_shape, prc=provider_lrc.prc)
                new_extra_lut_count = new_receiver_lrc.get_extra_lut_count(
                    r_logical_ram_mode)
                old_extra_lut_count = receiver_lrc.get_extra_lut_count(
                    r_logical_ram_mode)

                new_area = calculate_ram_area(
                    archs=self.archs(),
                    extra_lut_count=new_extra_lut_count)
                old_area = calculate_ram_area(
                    archs=self.archs(),
                    extra_lut_count=old_extra_lut_count,
                    prc=receiver_lrc.prc)

                saved_area = old_area - new_area
                sharing_pairs.append(
                    (saved_area/provider_free_bits, p_id, r_id))
        return sharing_pairs

    def find_final_sharing_pairs(self, sharing_pairs: List[Tuple[float, int, int]]) -> List[Tuple[float, int, int]]:
        # Determine final share list
        # (saved_area_per_bits, p_id, r_id)
        final_sharing_pairs: List[Tuple[float, int, int]] = list()

        # {p_id: {(saving, r_id)}}
        sharing_pairs_grouped: DefaultDict[int,
                                           Set[Tuple[float, int]]] = defaultdict(set)
        for saving, p_id, r_id in sharing_pairs:
            sharing_pairs_grouped[p_id].add((saving, r_id))

        while len(sharing_pairs_grouped) > 0:
            p_id = min(
                sharing_pairs_grouped.items(), key=lambda kv: len(kv[1]))[0]
            candidates_for_p_id = sharing_pairs_grouped[p_id]
            saving, r_id = max(candidates_for_p_id)
            final_sharing_pairs.append((saving, p_id, r_id))

            # Remove involved parties from sharing_pairs_grouped
            for other_p_id, other_pairs in list(sharing_pairs_grouped.items()):
                if other_p_id == p_id or other_p_id == r_id:
                    sharing_pairs_grouped.pop(other_p_id)
                else:
                    for other_saving, other_r_id in other_pairs.copy():
                        if other_r_id == p_id or other_r_id == r_id:
                            other_pairs.remove((other_saving, other_r_id))
                            if len(other_pairs) == 0:
                                sharing_pairs_grouped.pop(other_p_id)

        return final_sharing_pairs

    def solve(self, verbose: bool = False):
        # All possible lrc
        single_port_lrc_dict = self.find_single_port_lrcs()
        if verbose:
            logger.warning(
                f'{self.msg_header()}: single-port LRC list: {len(single_port_lrc_dict)}')
            for lrc in single_port_lrc_dict.values():
                logger.warning(f'{self.msg_header()}:  {lrc.serialize(0)}')

        # All possible lrc provider
        lrc_provider_list = self.find_provider_lrcs(
            single_port_lrc_dict=single_port_lrc_dict)
        if verbose:
            logger.info(
                f'{self.msg_header()}: single-port LRC with extra depth list: {len(lrc_provider_list)}')
            for lrc in lrc_provider_list:
                logger.warning(f'{self.msg_header()}:  {lrc.serialize(0)}')

        # Find sharing pair candidates, along with its gain
        sharing_pairs = self.find_sharing_pairs(
            single_port_lrc_dict=single_port_lrc_dict, lrc_provider_list=lrc_provider_list)
        if verbose:
            logger.info(
                f'{self.msg_header()}: sharing_pairs (saved_area_per_free_provider_bits, provider, receiver): {len(sharing_pairs)}')
            for delta, p_id, r_id in sharing_pairs:
                logger.warning(f'{self.msg_header()}:  {delta} {p_id} {r_id}')

        # Find final sharing pairs
        final_sharing_pairs = self.find_final_sharing_pairs(
            sharing_pairs=sharing_pairs)
        if verbose:
            logger.warning(
                f'{self.msg_header()}: final sharing_pairs (saved_area_per_free_provider_bits, provider, receiver): {len(final_sharing_pairs)}')
            for delta, p_id, r_id in final_sharing_pairs:
                logger.warning(f'{self.msg_header()}:  {delta} {p_id} {r_id}')

        # Apply final sharing pairs
        num_eliminated_physical_rams = 0
        for delta, p_id, r_id in final_sharing_pairs:
            provider_lrc = single_port_lrc_dict[p_id]
            receiver_lrc = single_port_lrc_dict[r_id]
            num_eliminated_physical_rams += receiver_lrc.prc.physical_shape_fit.get_count()
            provider_lrc.prc.ram_mode = RamMode.TrueDualPort
            receiver_lrc.prc = provider_lrc.prc
        logger.warning(
            f'{self.msg_header()}: Shared {len(final_sharing_pairs)} logical rams, ' +
            f'eliminated {num_eliminated_physical_rams} physical rams. ' +
            f'{len(single_port_lrc_dict)} single-port, ' +
            f'{len(lrc_provider_list)} providers')
