from collections import Counter
import copy
import logging
import random
from typing import Callable, Dict, List, Tuple

from .siv_heuristics import calculate_fpga_qor, calculate_fpga_qor_for_circuit, calculate_fpga_qor_for_ram_config

from .logical_ram import LogicalRam, RamShape, RamShapeFit
from .utils import T, sorted_dict_items
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
    solver = AllRamGreedyCircuitSolver(
        ram_archs=ram_archs,
        logical_circuit=logical_circuit,
        circuit_config=circuit_config,
        seed=circuit_config.circuit_id,
        physical_ram_uid=physical_ram_uid)
    solver.solve(num_steps=1000)
    circuit_config = solver.circuit_config()

    return circuit_config


def legal_ram_shape_fit_filter(fit: RamShapeFit) -> bool:
    return fit.num_series <= 16


def get_ram_shape_fits(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape) -> List[Tuple[RamShape, RamShapeFit]]:
    fits = ((physical_shape, target_logical_shape.get_fit(smaller_shape=physical_shape))
            for physical_shape in candidate_physical_shapes)
    return list(filter(lambda p: legal_ram_shape_fit_filter(p[1]), fits))


def find_min_ram_shape_fit(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape, key_funcs: List[Callable[[RamShape, RamShapeFit], T]]) -> List[RamShape]:
    '''
    key_func(physical_shape, shape_fit) -> Measure
    Union of mins keyed by key_funcs, return all if len(key_funcs) == 0
    '''
    shape_fit_pairs = get_ram_shape_fits(
        candidate_physical_shapes, target_logical_shape)
    if len(shape_fit_pairs) > 0:
        if len(key_funcs) == 0:
            return list(map(lambda p: p[0], shape_fit_pairs))
        else:
            return [min(shape_fit_pairs, key=lambda shape_fit: key_func(*shape_fit))[0] for key_func in key_funcs]
    else:
        return []


def get_wasted_bits(physical_shape: RamShape, fit: RamShapeFit, logical_shape: RamShape) -> int:
    total_physical_shape = RamShape(
        width=physical_shape.width*fit.num_parallel, depth=physical_shape.depth*fit.num_series)
    return total_physical_shape.get_size() - logical_shape.get_size()


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
        # Find candidates
        candidate_ram_arch_id_and_physical_shape_list = list()
        for ram_arch_id, ram_arch in sorted_dict_items(self.ram_archs()):
            if logical_ram.mode not in ram_arch.get_supported_mode():
                continue
            physical_shapes = ram_arch.get_shapes_for_mode(logical_ram.mode)
            candidate_physical_shapes = find_min_ram_shape_fit(
                physical_shapes, logical_ram.shape, key_funcs=optimizer_funcs)
            candidate_ram_arch_id_and_physical_shape_list.extend(
                map(lambda ps: (ram_arch_id, ps), candidate_physical_shapes))

        # Convert candidates into LogicalRamConfigs
        def convert_to_prc(ram_arch_id: int, physical_ram_shape: RamShape, physical_ram_uid: int = -1):
            prc = PhysicalRamConfig(
                id=physical_ram_uid,
                physical_shape_fit=logical_ram.shape.get_fit(
                    smaller_shape=physical_ram_shape),
                ram_arch_id=ram_arch_id,
                ram_mode=logical_ram.mode,
                physical_shape=physical_ram_shape)
            return prc
        candidate_prc_list = [convert_to_prc(ram_arch_id=ram_arch_id, physical_ram_shape=physical_shape)
                              for ram_arch_id, physical_shape in candidate_ram_arch_id_and_physical_shape_list]

        return candidate_prc_list


class AllRamGreedyCircuitSolver(CircuitSolverBase):
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, seed: int, physical_ram_uid: int):
        super().__init__(ram_archs=ram_archs,
                         logical_circuit=logical_circuit,
                         circuit_config=circuit_config,
                         physical_ram_uid=physical_ram_uid)
        self._rng = random.Random(seed)
        self._candidate_prc_list = {logical_ram_id: self.find_candidate_physical_ram_config_list(
            logical_ram=logical_ram, optimizer_funcs=[]) for logical_ram_id, logical_ram in sorted_dict_items(self.logical_circuit().rams)}

        self._extra_lut_count = self.circuit_config().get_extra_lut_count()
        self._physical_ram_count = self.circuit_config().get_physical_ram_count()
        self._fpga_area = self.calculate_fpga_area()

    def propose_evaluate_single_physical_ram_config(self) -> bool:
        '''
        Return True if new prc is accepted; otherwise False
        '''
        logical_ram_id, rc = self._rng.choice(
            list(sorted_dict_items(self.circuit_config().rams)))
        debug_str = f'logical_ram={logical_ram_id}'

        # Save old
        prc_old = rc.lrc.prc
        area_old = self._fpga_area

        # Randomly pick a prc
        prc_new = copy.deepcopy(self._rng.choice(
            self.get_candidate_prc(logical_ram_id=logical_ram_id)))
        prc_new.id = prc_old.id

        def extra_luts(prc: PhysicalRamConfig) -> int:
            return determine_extra_luts(num_series=prc.physical_shape_fit.num_series, logical_w=rc.lrc.logical_shape.width, ram_mode=prc.ram_mode)

        new_extra_lut_count = self._extra_lut_count - \
            extra_luts(prc_old) + extra_luts(prc_new)
        new_physical_ram_count = self._physical_ram_count - \
            prc_old.get_physical_ram_count() + prc_new.get_physical_ram_count()

        # Install new
        rc.lrc.prc = prc_new
        area_new = self.calculate_fpga_area_fast(
            extra_lut_count=new_extra_lut_count, physical_ram_count=new_physical_ram_count)

        # If new is worse than old, revert
        debug_str += f': area_new={area_new}, area_old={area_old}'
        should_reject = area_new >= area_old
        if should_reject:
            debug_str += ' rejected'
            rc.lrc.prc = prc_old
        else:
            self._extra_lut_count = new_extra_lut_count
            self._physical_ram_count = new_physical_ram_count
            self._fpga_area = area_new
            debug_str += ' accepted'
        logging.debug(f'{debug_str}')

        return not should_reject

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

    def solve(self, num_steps: int):
        num_accepted = 0
        for step in range(num_steps):
            logging.debug(f'- step={step} / {num_steps} -')
            is_accepted = self.propose_evaluate_single_physical_ram_config()
            if is_accepted:
                num_accepted += 1
        logging.info(
            f'{num_steps} finished, {num_accepted} accepted ({num_accepted/num_steps*100:.2f}%)')


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

    def solve(self) -> CircuitConfig:
        self.circuit_config().rams.clear()
        for _, lr in sorted_dict_items(self.logical_circuit().rams):
            self.circuit_config().insert_ram_config(self.solve_single_ram(logical_ram=lr))
