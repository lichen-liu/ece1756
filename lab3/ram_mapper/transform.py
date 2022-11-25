from collections import Counter
from enum import Enum, auto
import logging
import math
import random
from typing import Callable, Dict, List, NamedTuple, Tuple

from .siv_heuristics import calculate_fpga_qor, calculate_fpga_qor_for_circuit, calculate_fpga_qor_for_ram_config

from .logical_ram import LogicalRam, RamShape, RamShapeFit
from .utils import T, sigmoid, sorted_dict_items
from .mapping_config import AllCircuitConfig, CircuitConfig, LogicalRamConfig, PhysicalRamConfig, RamConfig
from .logical_circuit import LogicalCircuit
from .siv_arch import SIVRamArch, determine_extra_luts


def solve_all_circuits(ram_archs: Dict[int, SIVRamArch], logical_circuits: Dict[int, LogicalCircuit]) -> AllCircuitConfig:
    acc = AllCircuitConfig()
    num_circuits = len(logical_circuits)
    for circuit_id, lc in sorted_dict_items(logical_circuits):
        logging.warning(f'Solving circuit {circuit_id} out of {num_circuits}')
        acc.insert_circuit_config(solve_single_circuit(
            ram_archs=ram_archs, logical_circuit=lc))
    return acc


def solve_single_circuit(ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit) -> CircuitConfig:
    # Generate an initial config
    solver = PerRamGreedyCircuitSolver(
        ram_archs=ram_archs,
        logical_circuit=logical_circuit)
    solver.solve()
    circuit_config = solver.circuit_config()
    physical_ram_uid = solver.assign_physical_ram_uid()

    # Incrementally improving
    solver = AnnealingCircuitSolver(
        ram_archs=ram_archs,
        logical_circuit=logical_circuit,
        circuit_config=circuit_config,
        seed=circuit_config.circuit_id,
        physical_ram_uid=physical_ram_uid)

    initial_temperature = 1
    exploration_factor = 10
    # target_acceptance_ratio = 0.1
    # acceptance_adjustment_starting_step_fraction = 1
    quench_starting_step_fraction = 0.95

    search_space_size = solver.get_search_space_size()
    num_steps = search_space_size * exploration_factor
    logging.info(
        f'{num_steps} steps ({exploration_factor} * {search_space_size}), starting at temperature {initial_temperature}')

    def temperature_schedule(param: TemperatureScheduleParam) -> float:
        step_fraction = param.current_step_fraction()
        step_fraction_left = 1 - step_fraction
        # Ensure quenching
        if step_fraction >= quench_starting_step_fraction:
            # logging.info(f'0')
            return 0
        else:
            # todo
            # current_temperature = step_fraction_left * step_fraction_left * initial_temperature
            current_temperature = initial_temperature / \
                (param.current_step + 1)
            # acceptance_ratio = param.acceptance_ratio()
            # if step_fraction >= acceptance_adjustment_starting_step_fraction:
            #     current_temperature *= 2 * \
            #         sigmoid(target_acceptance_ratio - acceptance_ratio)
            # logging.info(f'{current_temperature}')
            return current_temperature

    solver.solve(num_steps=num_steps,
                 temperature_schedule=temperature_schedule, stats=False)
    circuit_config = solver.circuit_config()

    # assert False

    return circuit_config


def legal_ram_shape_fit_filter(fit: RamShapeFit) -> bool:
    return fit.num_series <= 16


def get_ram_shape_fits(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape) -> List[Tuple[RamShape, RamShapeFit]]:
    fits = [(physical_shape, fit)
            for physical_shape in candidate_physical_shapes if legal_ram_shape_fit_filter(fit := target_logical_shape.get_fit(smaller_shape=physical_shape))]
    return fits


def find_min_ram_shape_fit(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape, key_funcs: List[Callable[[RamShape, RamShapeFit], T]]) -> List[Tuple[RamShape, RamShapeFit]]:
    '''
    key_func(physical_shape, shape_fit) -> Measure
    Union of mins keyed by key_funcs, return all if len(key_funcs) == 0
    '''
    shape_fit_pairs = get_ram_shape_fits(
        candidate_physical_shapes, target_logical_shape)
    if len(shape_fit_pairs) > 0:
        if len(key_funcs) == 0:
            return shape_fit_pairs
        else:
            return list(set(min(shape_fit_pairs, key=lambda shape_fit: key_func(*shape_fit)) for key_func in key_funcs))
    else:
        return []


class CircuitSolverBase:
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, physical_ram_uid: int):
        self._ram_archs = ram_archs
        self._logical_circuit = logical_circuit
        self._physical_ram_uid = physical_ram_uid
        self._circuit_config = circuit_config

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

    def find_candidate_physical_ram_config_list(self, logical_ram: LogicalRam, optimizer_funcs: List[Callable[[RamShape, RamShapeFit], T]]) -> List[PhysicalRamConfig]:
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
        for ram_arch in self.ram_archs().values():
            if logical_ram.mode not in ram_arch.get_supported_mode():
                continue
            physical_shapes = ram_arch.get_shapes_for_mode(logical_ram.mode)
            candidate_physical_shape_fits = find_min_ram_shape_fit(
                physical_shapes, logical_ram.shape, key_funcs=optimizer_funcs)
            candidate_prc_list.extend(
                map(lambda psf: convert_to_prc(ram_arch_id=ram_arch.get_id(), physical_ram_shape=psf[0], physical_ram_shape_fit=psf[1]), candidate_physical_shape_fits))

        return candidate_prc_list


class TemperatureScheduleParam(NamedTuple):
    num_steps: int
    current_step: int
    prev_temperature: float
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


class AnnealingCircuitSolver(CircuitSolverBase):
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, seed: int, physical_ram_uid: int):
        super().__init__(ram_archs=ram_archs,
                         logical_circuit=logical_circuit,
                         circuit_config=circuit_config,
                         physical_ram_uid=physical_ram_uid)
        # RNG
        self._rng = random.Random(seed)

        # Search space
        self._candidate_prc_list = {logical_ram.ram_id: self.find_candidate_physical_ram_config_list(
            logical_ram=logical_ram, optimizer_funcs=[]) for logical_ram in self.logical_circuit().rams.values()}
        self._candidate_prc_size = sum(
            map(lambda prc_list: len(prc_list), self._candidate_prc_list.values()))

        # Area calculation
        self._extra_lut_count = self.circuit_config().get_extra_lut_count()
        self._physical_ram_count = self.circuit_config().get_physical_ram_count()
        self._fpga_area = self.calculate_fpga_area()

    def get_search_space_size(self) -> int:
        return self._candidate_prc_size

    def propose_evaluate_single_physical_ram_config(self, should_accept_func: Callable[[int, int], bool]) -> MoveOutcome:
        '''
        should_accept_func(new_area,old_area)
        Return True if new prc is accepted; otherwise False
        '''
        rc = self._rng.choice(list(self.circuit_config().rams.values()))

        # Save old
        prc_old = rc.lrc.prc
        # Get old area
        area_old = self._fpga_area

        # Randomly pick a new prc
        prc_new = self._rng.choice(
            self.get_candidate_prc(logical_ram_id=rc.ram_id))
        if prc_old is prc_new:
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

        # If new is better than old, apply the change
        if area_new < area_old:
            apply_move()
            return MoveOutcome.ACCEPTED_AREA

        if should_accept_func(area_new, area_old):
            apply_move()
            return MoveOutcome.ACCEPTED_TEMPERATURE

        return MoveOutcome.REJECTED_AREA

    def get_candidate_prc(self, logical_ram_id: int) -> List[PhysicalRamConfig]:
        return self._candidate_prc_list[logical_ram_id]

    def calculate_fpga_area(self) -> int:
        return calculate_fpga_qor_for_circuit(ram_archs=self.ram_archs(), logical_circuit=self.logical_circuit(), circuit_config=self.circuit_config()).fpga_area

    def calculate_fpga_area_fast(self, extra_lut_count: int, physical_ram_count: Counter[int]) -> int:
        qor = calculate_fpga_qor(
            ram_archs=self.ram_archs(),
            logic_block_count=self.logical_circuit().num_logic_blocks,
            extra_lut_count=extra_lut_count,
            physical_ram_count=physical_ram_count)
        return qor.fpga_area

    def solve(self, num_steps: int, temperature_schedule: Callable[[TemperatureScheduleParam], float], stats: bool = False):
        outcome_stats = Counter()
        num_accepted = 0
        prev_temperature = -1
        for step in range(num_steps):
            t_schedule_param = TemperatureScheduleParam(
                num_steps=num_steps, current_step=step, prev_temperature=prev_temperature, num_accepted=num_accepted)
            temperature = temperature_schedule(t_schedule_param)

            def should_accept(new_area: int, old_area: int) -> bool:
                return temperature > 0 and self._rng.uniform(0, 1) < math.exp(-((new_area - old_area)/old_area)/temperature)

            logging.debug(
                f'- step={step} (total={num_steps}) temperature={temperature} -')
            outcome = self.propose_evaluate_single_physical_ram_config(
                should_accept)

            # Book-keeping
            if outcome.is_accepted():
                num_accepted += 1
            if stats:
                outcome_stats[outcome] += 1
            prev_temperature = temperature

        logging.info(
            f'{num_steps} steps finished, {num_accepted} accepted ({num_accepted/num_steps*100:.2f}%)')
        if stats:
            logging.info(f'    Stats {str(outcome_stats)}')


class PerRamGreedyCircuitSolver(CircuitSolverBase):
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit):
        super().__init__(ram_archs=ram_archs,
                         logical_circuit=logical_circuit,
                         circuit_config=CircuitConfig(
                             circuit_id=logical_circuit.circuit_id),
                         physical_ram_uid=0)

    def solve_single_ram(self, logical_ram: LogicalRam) -> RamConfig:
        def find_min_count(physical_shape, fit):
            return (fit.get_count(), fit.num_series)

        def find_min_series(physical_shape, fit):
            return (fit.num_series, fit.get_count())

        candidate_prc_list = self.find_candidate_physical_ram_config_list(
            logical_ram=logical_ram, optimizer_funcs=[find_min_count, find_min_series])
        candidate_lrc_list = list(map(lambda prc: LogicalRamConfig(
            logical_shape=logical_ram.shape, prc=prc), candidate_prc_list))

        # Calculate aspect ram area
        area_list = [calculate_fpga_qor_for_ram_config(
            ram_archs=self.ram_archs(), logic_block_count=0, logical_ram_config=lrc, verbose=False).fpga_area for lrc in candidate_lrc_list]
        candidate_lrc_area_list = list(
            zip(candidate_lrc_list, area_list))
        logging.debug('Candidates:')
        for lrc, area in candidate_lrc_area_list:
            logging.debug(f'{lrc.serialize(0)} ASPECTED_AREA={area}')

        # Find best candidate
        best_lrc, best_fpga_area = min(candidate_lrc_area_list,
                                       key=lambda lrc_area: lrc_area[1])

        # Finalize the best candidate
        # best_lrc = copy.deepcopy(best_lrc)
        best_lrc.prc.id = self.assign_physical_ram_uid()
        logging.debug('Best:')
        logging.debug(
            f'{best_lrc.serialize(0)} ASPECTED_AREA={best_fpga_area}')

        return RamConfig(circuit_id=logical_ram.circuit_id, ram_id=logical_ram.ram_id, lrc=best_lrc)

    def solve(self):
        self.circuit_config().rams.clear()
        for _, lr in sorted_dict_items(self.logical_circuit().rams):
            self.circuit_config().insert_ram_config(self.solve_single_ram(logical_ram=lr))
