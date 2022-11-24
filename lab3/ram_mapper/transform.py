import logging
from typing import Callable, Dict, List, Tuple

from .siv_heuristics import calculate_fpga_area_for_ram_config

from .logical_ram import LogicalRam, RamShape, RamShapeFit
from .utils import T, sorted_dict_items
from .mapping_config import AllCircuitConfig, CircuitConfig, LogicalRamConfig, PhysicalRamConfig, RamConfig
from .logical_circuit import LogicalCircuit
from .siv_arch import SIVRamArch


def solve_all_circuits(ram_archs: Dict[int, SIVRamArch], logical_circuits: Dict[int, LogicalCircuit]) -> AllCircuitConfig:
    acc = AllCircuitConfig()
    for _, lc in sorted_dict_items(logical_circuits):
        acc.insert_circuit_config(solve_single_circuit(
            ram_archs=ram_archs, logical_circuit=lc))
    return acc


def solve_single_circuit(ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit) -> CircuitConfig:
    simple_circuit_solver = FullCircuitSolver(ram_archs=ram_archs)
    return simple_circuit_solver.solve(logical_circuit=logical_circuit)


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


def get_waste_bits(physical_shape: RamShape, fit: RamShapeFit, logical_shape: RamShape) -> int:
    total_physical_shape = RamShape(
        width=physical_shape.width*fit.num_parallel, depth=physical_shape.depth*fit.num_series)
    return total_physical_shape.get_size() - logical_shape.get_size()


class SimpleCircuitSolver:
    def __init__(self, ram_archs: Dict[int, SIVRamArch]):
        self._ram_archs = ram_archs
        self._physical_ram_uid = 0

    def assign_physical_ram_uid(self) -> int:
        assigned_value = self._physical_ram_uid
        self._physical_ram_uid += 1
        return assigned_value

    def solve_single_ram(self, logical_ram: LogicalRam) -> RamConfig:
        def find_min_count(physical_shape, fit):
            return (fit.get_count(), fit.num_series)

        def find_min_series(physical_shape, fit):
            return (fit.num_series, fit.get_count())

        # Find candidates
        candidate_ram_arch_id_and_physical_shape_list = list()
        for ram_arch_id, ram_arch in sorted_dict_items(self._ram_archs):
            if logical_ram.mode not in ram_arch.get_supported_mode():
                continue
            physical_shapes = ram_arch.get_shapes_for_mode(logical_ram.mode)
            optimizer_funcs = [find_min_count, find_min_series]
            candidate_physical_shapes = find_min_ram_shape_fit(
                physical_shapes, logical_ram.shape, key_funcs=optimizer_funcs)
            candidate_ram_arch_id_and_physical_shape_list.extend(
                map(lambda ps: (ram_arch_id, ps), candidate_physical_shapes))

        # Convert candidates into LogicalRamConfigs
        def convert_to_lrc(ram_arch_id: int, physical_shape: RamShape):
            prc = PhysicalRamConfig(
                id=-1,
                physical_shape_fit=logical_ram.shape.get_fit(
                    smaller_shape=physical_shape),
                ram_arch_id=ram_arch_id,
                ram_mode=logical_ram.mode,
                physical_shape=physical_shape)
            return LogicalRamConfig(logical_shape=logical_ram.shape, prc=prc)
        candidate_lrc_list = [convert_to_lrc(ram_arch_id=ram_arch_id, physical_shape=physical_shape)
                              for ram_arch_id, physical_shape in candidate_ram_arch_id_and_physical_shape_list]

        # Calculate aspect ram area
        area_list = [calculate_fpga_area_for_ram_config(
            ram_archs=self._ram_archs, logic_block_count=0, logical_ram_config=lrc, verbose=False)for lrc in candidate_lrc_list]
        candidate_lrc_area_list = list(
            zip(candidate_lrc_list, area_list))
        logging.debug('Candidates:')
        for lrc, area in candidate_lrc_area_list:
            logging.debug(f'{lrc.serialize(0)} ASPECTED_AREA={area}')

        # Find best candidate
        best_lrc, best_fpga_area = min(candidate_lrc_area_list,
                                       key=lambda lrc_area: lrc_area[1])

        # Finalize the best candidate
        best_lrc.prc.id = self.assign_physical_ram_uid()
        logging.debug('Best:')
        logging.debug(
            f'{best_lrc.serialize(0)} ASPECTED_AREA={best_fpga_area}')

        return RamConfig(circuit_id=logical_ram.circuit_id, ram_id=logical_ram.ram_id, lrc=best_lrc)

    def solve(self, logical_circuit: LogicalCircuit) -> CircuitConfig:
        cc = CircuitConfig(circuit_id=logical_circuit.circuit_id)
        for _, lr in sorted_dict_items(logical_circuit.rams):
            cc.insert_ram_config(self.solve_single_ram(logical_ram=lr))
        return cc


class FullCircuitSolver:
    def __init__(self, ram_archs: Dict[int, SIVRamArch]):
        self._ram_archs = ram_archs
        self._physical_ram_uid = 0

    def assign_physical_ram_uid(self) -> int:
        assigned_value = self._physical_ram_uid
        self._physical_ram_uid += 1
        return assigned_value

    def solve_single_ram(self, logical_ram: LogicalRam) -> RamConfig:
        def find_min_count(physical_shape, fit):
            return (fit.get_count(), fit.num_series)

        def find_min_series(physical_shape, fit):
            return (fit.num_series, fit.get_count())

        # Find candidates
        candidate_ram_arch_id_and_physical_shape_list = list()
        for ram_arch_id, ram_arch in sorted_dict_items(self._ram_archs):
            if logical_ram.mode not in ram_arch.get_supported_mode():
                continue
            physical_shapes = ram_arch.get_shapes_for_mode(logical_ram.mode)
            optimizer_funcs = [find_min_count, find_min_series]
            candidate_physical_shapes = find_min_ram_shape_fit(
                physical_shapes, logical_ram.shape, key_funcs=optimizer_funcs)
            candidate_ram_arch_id_and_physical_shape_list.extend(
                map(lambda ps: (ram_arch_id, ps), candidate_physical_shapes))

        # Convert candidates into LogicalRamConfigs
        def convert_to_lrc(ram_arch_id: int, physical_shape: RamShape):
            prc = PhysicalRamConfig(
                id=-1,
                physical_shape_fit=logical_ram.shape.get_fit(
                    smaller_shape=physical_shape),
                ram_arch_id=ram_arch_id,
                ram_mode=logical_ram.mode,
                physical_shape=physical_shape)
            return LogicalRamConfig(logical_shape=logical_ram.shape, prc=prc)
        candidate_lrc_list = [convert_to_lrc(ram_arch_id=ram_arch_id, physical_shape=physical_shape)
                              for ram_arch_id, physical_shape in candidate_ram_arch_id_and_physical_shape_list]

        # Calculate aspect ram area
        area_list = [calculate_fpga_area_for_ram_config(
            ram_archs=self._ram_archs, logic_block_count=0, logical_ram_config=lrc, verbose=False)for lrc in candidate_lrc_list]
        candidate_lrc_area_list = list(
            zip(candidate_lrc_list, area_list))
        logging.debug('Candidates:')
        for lrc, area in candidate_lrc_area_list:
            logging.debug(f'{lrc.serialize(0)} ASPECTED_AREA={area}')

        # Find best candidate
        best_lrc, best_fpga_area = min(candidate_lrc_area_list,
                                       key=lambda lrc_area: lrc_area[1])

        # Finalize the best candidate
        best_lrc.prc.id = self.assign_physical_ram_uid()
        logging.debug('Best:')
        logging.debug(
            f'{best_lrc.serialize(0)} ASPECTED_AREA={best_fpga_area}')

        return RamConfig(circuit_id=logical_ram.circuit_id, ram_id=logical_ram.ram_id, lrc=best_lrc)

    def solve(self, logical_circuit: LogicalCircuit) -> CircuitConfig:
        cc = CircuitConfig(circuit_id=logical_circuit.circuit_id)
        for _, lr in sorted_dict_items(logical_circuit.rams):
            cc.insert_ram_config(self.solve_single_ram(logical_ram=lr))
        return cc
