from collections import Counter
import copy
from enum import Enum, auto
from itertools import starmap
import logging
import math
import random
from typing import Callable, Dict, Iterable, Iterator, List, NamedTuple, Tuple


from .siv_heuristics import calculate_fpga_qor, calculate_fpga_qor_for_circuit, calculate_fpga_qor_for_ram_config

from .logical_ram import LogicalRam, RamShape, RamShapeFit
from .utils import sorted_dict_items, proccess_initializer
from .mapping_config import AllCircuitConfig, CircuitConfig, LogicalRamConfig, PhysicalRamConfig, RamConfig
from .logical_circuit import LogicalCircuit
from .siv_arch import SIVRamArch, determine_extra_luts
from multiprocessing import Pool


def solve_all_circuits(ram_archs: Dict[int, SIVRamArch], logical_circuits: Dict[int, LogicalCircuit], args) -> AllCircuitConfig:
    num_circuits = len(logical_circuits)
    logging.warning(
        f'Solving for {num_circuits} circuits using {args.processes} processes')

    acc = AllCircuitConfig()

    def starmap_dispatcher(starmap_func):
        circuit_configs = starmap_func(solve_single_circuit, map(
            lambda lc: (ram_archs, lc), logical_circuits.values()))
        for circuit_config in circuit_configs:
            acc.insert_circuit_config(cc=circuit_config)

    if args.processes == 1:
        starmap_dispatcher(starmap_func=starmap)
    else:
        with Pool(processes=args.processes, initializer=proccess_initializer, initargs=(args,)) as p:
            starmap_dispatcher(starmap_func=p.starmap)
    return acc


def solve_single_circuit(ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit) -> CircuitConfig:
    prc_candidates = generate_candidate_prc_for_lc(
        ram_archs=ram_archs, logical_circuit=logical_circuit)

    # Generate an initial config
    solver = SingleLevelCircuitInitialSolution(
        ram_archs=ram_archs,
        logical_circuit=logical_circuit,
        prc_candidates=prc_candidates)
    solver.solve()
    circuit_config = solver.circuit_config()
    physical_ram_uid = solver.assign_physical_ram_uid()

    # Incrementally improving
    solver = SingleLevelCircuitOptimizer(
        ram_archs=ram_archs,
        logical_circuit=logical_circuit,
        circuit_config=circuit_config,
        seed=circuit_config.circuit_id,
        physical_ram_uid=physical_ram_uid,
        prc_candidates=prc_candidates)
    solver.solve()
    circuit_config = solver.circuit_config()

    # assert False

    return circuit_config


def legal_ram_shape_fit_filter(fit: RamShapeFit) -> bool:
    return fit.num_series <= 16


def get_ram_shape_fits(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape) -> Iterator[Tuple[RamShape, RamShapeFit]]:
    return ((physical_shape, fit)
            for physical_shape in candidate_physical_shapes if legal_ram_shape_fit_filter(fit := target_logical_shape.get_fit(smaller_shape=physical_shape)))


def generate_candidate_prc_for_lr(ram_archs: Dict[int, SIVRamArch], logical_ram: LogicalRam) -> List[PhysicalRamConfig]:
    # Convert candidates into LogicalRamConfigs
    def convert_to_prc(ram_arch_id: int, physical_ram_shape: RamShape, physical_ram_shape_fit: RamShapeFit):
        prc = PhysicalRamConfig(
            id=-1,
            physical_shape_fit=physical_ram_shape_fit,
            ram_arch_id=ram_arch_id,
            ram_mode=logical_ram.mode,
            physical_shape=physical_ram_shape)
        return prc

    # Find candidates
    candidate_prc_list = list()
    for ram_arch in ram_archs.values():
        if logical_ram.mode not in ram_arch.get_supported_mode():
            continue
        physical_shapes = ram_arch.get_shapes_for_mode(logical_ram.mode)
        candidate_physical_shape_fits = get_ram_shape_fits(
            candidate_physical_shapes=physical_shapes, target_logical_shape=logical_ram.shape)
        candidate_prc_list.extend(
            map(lambda psf: convert_to_prc(ram_arch_id=ram_arch.get_id(), physical_ram_shape=psf[0], physical_ram_shape_fit=psf[1]), candidate_physical_shape_fits))

    return candidate_prc_list


def generate_candidate_prc_for_lc(ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit) -> Dict[int, List[PhysicalRamConfig]]:
    return {logical_ram.ram_id: generate_candidate_prc_for_lr(ram_archs=ram_archs, logical_ram=logical_ram) for logical_ram in logical_circuit.rams.values()}


class CircuitSolverBase:
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, physical_ram_uid: int, prc_candidates: Dict[int, List[PhysicalRamConfig]]):
        self._ram_archs = ram_archs
        self._logical_circuit = logical_circuit
        self._physical_ram_uid = physical_ram_uid
        self._circuit_config = circuit_config
        self._prc_candidates = prc_candidates

    def get_candidate_prc(self, logical_ram_id: int) -> List[PhysicalRamConfig]:
        return self._prc_candidates[logical_ram_id]

    def circuit_config(self) -> CircuitConfig:
        return self._circuit_config

    def logical_circuit(self) -> LogicalCircuit:
        return self._logical_circuit

    def ram_archs(self) -> Dict[int, SIVRamArch]:
        return self._ram_archs

    def assign_physical_ram_uid(self) -> int:
        assigned_value = self._physical_ram_uid
        self._physical_ram_uid += 1
        return assigned_value


class TemperatureScheduleParam(NamedTuple):
    num_steps: int
    current_step: int
    num_accepted: int

    def current_step_fraction(self) -> float:
        return (self.current_step + 1) / self.num_steps

    def acceptance_ratio(self) -> float:
        return 0 if self.current_step == 0 else self.num_accepted/self.current_step


class MoveOutcome(Enum):
    ACCEPTED_AREA = auto()
    ACCEPTED_TEMPERATURE = auto()
    REJECTED_AREA = auto()
    ABORT_DUPLICATED = auto()

    def is_accepted(self) -> bool:
        return self == self.ACCEPTED_AREA or self == self.ACCEPTED_TEMPERATURE


class SingleLevelCircuitOptimizer(CircuitSolverBase):
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, seed: int, physical_ram_uid: int, prc_candidates: Dict[int, List[PhysicalRamConfig]]):
        super().__init__(ram_archs=ram_archs,
                         logical_circuit=logical_circuit,
                         circuit_config=circuit_config,
                         physical_ram_uid=physical_ram_uid,
                         prc_candidates=prc_candidates)
        # RNG
        self._rng = random.Random(seed)

        # Search space
        self._candidate_prc_size = sum(
            map(lambda prc_list: len(prc_list), prc_candidates.values()))

        # Area calculation
        self.prepare_area_calculation_cache()
        # Save the best copy
        self._enable_save_best = False
        self._best_fpga_area_saved = self._fpga_area
        if self._enable_save_best:
            self._best_circuit_config_saved = copy.deepcopy(
                self.circuit_config())

    def prepare_area_calculation_cache(self):
        self._extra_lut_count = self.circuit_config().get_extra_lut_count()
        self._physical_ram_count = self.circuit_config().get_physical_ram_count()
        self._fpga_area = self.calculate_fpga_area()

    def switch_to_best_circuit_config(self):
        assert self._enable_save_best
        if self._best_fpga_area_saved < self._fpga_area:
            self._circuit_config = self._best_circuit_config_saved
            self.prepare_area_calculation_cache()

    def get_search_space_size(self) -> int:
        return self._candidate_prc_size

    def select_rc_to_move(self) -> RamConfig:
        return self._rng.choice(list(self.circuit_config().rams.values()))

    def propose_move(self, rc: RamConfig) -> PhysicalRamConfig:
        # Randomly pick a new prc
        return self._rng.choice(
            self.get_candidate_prc(logical_ram_id=rc.ram_id))

    def evaluate_apply_move(self, rc: RamConfig, prc_new: PhysicalRamConfig, should_accept_worse_func: Callable[[int, int], bool]) -> MoveOutcome:
        '''
        should_accept_worse_func(new_area,old_area)
        Return True if new prc is accepted; otherwise False
        '''
        # Save old
        prc_old = rc.lrc.prc
        # Get old area
        area_old = self._fpga_area

        if prc_old == prc_new:
            return MoveOutcome.ABORT_DUPLICATED

        # Calculate new area
        def extra_luts(prc: PhysicalRamConfig) -> int:
            return determine_extra_luts(num_series=prc.physical_shape_fit.num_series, logical_w=rc.lrc.logical_shape.width, ram_mode=prc.ram_mode)
        new_extra_lut_count = self._extra_lut_count - \
            extra_luts(prc_old) + extra_luts(prc_new)
        new_physical_ram_count = self._physical_ram_count - \
            prc_old.get_physical_ram_count() + prc_new.get_physical_ram_count()
        area_new = self.calculate_fpga_area_fast(
            extra_lut_count=new_extra_lut_count, physical_ram_count=new_physical_ram_count)

        def apply_move():
            # Install new
            prc_new.id = prc_old.id
            rc.lrc.prc = prc_new
            # Update area
            self._extra_lut_count = new_extra_lut_count
            self._physical_ram_count = new_physical_ram_count
            self._fpga_area = area_new
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

        if should_accept_worse_func(area_new, area_old):
            apply_move()
            return MoveOutcome.ACCEPTED_TEMPERATURE

        return MoveOutcome.REJECTED_AREA

    def propose_evaluate_single_prc(self, should_accept_worse_func: Callable[[int, int], bool]) -> MoveOutcome:
        '''
        should_accept_worse_func(new_area,old_area)
        Return True if new prc is accepted; otherwise False
        '''
        rc = self.select_rc_to_move()

        # Randomly pick a new prc
        prc_new = self.propose_move(rc=rc)

        return self.evaluate_apply_move(rc=rc, prc_new=prc_new, should_accept_worse_func=should_accept_worse_func)

    def calculate_fpga_area(self) -> int:
        return calculate_fpga_qor_for_circuit(ram_archs=self.ram_archs(), logical_circuit=self.logical_circuit(), circuit_config=self.circuit_config()).fpga_area

    def calculate_fpga_area_fast(self, extra_lut_count: int, physical_ram_count: Counter[int]) -> int:
        qor = calculate_fpga_qor(
            ram_archs=self.ram_archs(),
            logic_block_count=self.logical_circuit().num_logic_blocks,
            extra_lut_count=extra_lut_count,
            physical_ram_count=physical_ram_count)
        return qor.fpga_area

    def solve(self):
        # Hillclimb
        # -------param-------
        exploration_factor = 40
        max_outer_loop = 20
        initial_temperature = 50
        target_acceptance_ratio = 0.1
        quench_starting_step_fraction = 0.95
        # -------param-------
        search_space_size = self.get_search_space_size()
        num_steps = search_space_size * exploration_factor

        logging.info(
            f'circuit {self.logical_circuit().circuit_id} HC: {num_steps} steps ({exploration_factor} * {search_space_size}), starting at temperature {initial_temperature}')

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

        self.greedy()

    def anneal(self, num_steps: int, target_acceptance_ratio: float, max_outer_loop: int, temperature_schedule: Callable[[TemperatureScheduleParam], float], stats: bool = False):
        outcome_stats = Counter()
        num_accepted = 0
        steps_performed = 0
        total_steps_to_perform = 0

        for _ in range(max_outer_loop):
            total_steps_to_perform += num_steps
            for _ in range(num_steps):
                # Only executes when needed
                def should_accept_worse(new_area: int, old_area: int) -> bool:
                    # Only computed when needed, temperature_schedule must not be dependening on previous states
                    temperature = temperature_schedule(
                        TemperatureScheduleParam(num_steps=total_steps_to_perform, current_step=steps_performed, num_accepted=num_accepted))
                    return temperature > 0 and self._rng.uniform(0, 1) < math.exp(-((new_area - old_area)/old_area)/temperature)

                outcome = self.propose_evaluate_single_prc(should_accept_worse)

                # Book-keeping
                if outcome.is_accepted():
                    num_accepted += 1
                if stats:
                    outcome_stats[outcome] += 1
                steps_performed += 1

            current_acceptance_ratio = num_accepted/steps_performed
            if current_acceptance_ratio > target_acceptance_ratio:
                logging.info(
                    f'circuit {self.logical_circuit().circuit_id} HC: ' +
                    f'extends {num_steps} steps ({steps_performed} / {total_steps_to_perform+num_steps}) ' +
                    f'b/c acceptance ratio {current_acceptance_ratio} > target {target_acceptance_ratio} ' +
                    f'at temperature {temperature_schedule(TemperatureScheduleParam(num_steps=total_steps_to_perform+num_steps, current_step=steps_performed, num_accepted=num_accepted))}')
            else:
                break
        logging.warning(
            f'circuit {self.logical_circuit().circuit_id} HC: ' +
            f'{steps_performed} steps finished (originally {num_steps}), {num_accepted} accepted ({num_accepted/steps_performed*100:.2f}%) ' +
            f'fina_area={self._fpga_area} best_area={self._best_fpga_area_saved} (Match={self._fpga_area==self._best_fpga_area_saved})')
        if stats:
            logging.info(f'    Stats {str(outcome_stats)}')

    def greedy(self):
        is_converged = False
        convergence_loop_counter = 0
        num_accepted = 0
        while not is_converged:
            is_converged = True
            for _, rc in sorted_dict_items(self.circuit_config().rams):
                for prc_new in self.get_candidate_prc(logical_ram_id=rc.ram_id):
                    outcome = self.evaluate_apply_move(
                        rc=rc, prc_new=prc_new, should_accept_worse_func=lambda _a, _b: False)
                    if outcome.is_accepted():
                        is_converged = False
                        num_accepted += 1
            convergence_loop_counter += 1

        search_space_size = self.get_search_space_size()
        steps_performed = convergence_loop_counter * search_space_size
        logging.warning(
            f'circuit {self.logical_circuit().circuit_id} Q Converged: ' +
            f'{convergence_loop_counter} * {search_space_size} = {steps_performed} steps finished, {num_accepted} accepted ({num_accepted/steps_performed*100:.2f}%) ' +
            f'final_area={self._fpga_area} best_area={self._best_fpga_area_saved} (Match={self._fpga_area==self._best_fpga_area_saved})')


class SingleLevelCircuitInitialSolution(CircuitSolverBase):
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, prc_candidates: Dict[int, List[PhysicalRamConfig]]):
        super().__init__(ram_archs=ram_archs,
                         logical_circuit=logical_circuit,
                         circuit_config=CircuitConfig(
                             circuit_id=logical_circuit.circuit_id),
                         physical_ram_uid=0,
                         prc_candidates=prc_candidates)

    def solve_single_ram(self, logical_ram: LogicalRam) -> RamConfig:
        candidate_lrc_list = map(lambda prc: LogicalRamConfig(
            logical_shape=logical_ram.shape, prc=prc), self.get_candidate_prc(logical_ram_id=logical_ram.ram_id))

        def area_estimator(lrc: LogicalRamConfig) -> int:
            return calculate_fpga_qor_for_ram_config(ram_archs=self.ram_archs(), logic_block_count=0, logical_ram_config=lrc).fpga_area
        best_candidate_lrc = min(map(lambda lrc: (lrc, area_estimator(
            lrc)), candidate_lrc_list), key=lambda p: p[1])[0]
        # Finalize the best candidate
        best_candidate_lrc.prc.id = self.assign_physical_ram_uid()
        return RamConfig(circuit_id=logical_ram.circuit_id, ram_id=logical_ram.ram_id, lrc=best_candidate_lrc)

    def solve(self):
        self.circuit_config().rams.clear()
        for _, lr in sorted_dict_items(self.logical_circuit().rams):
            self.circuit_config().insert_ram_config(self.solve_single_ram(logical_ram=lr))
