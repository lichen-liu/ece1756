from typing import Callable, Dict, List

from .logical_ram import RamShape, RamShapeFit
from .utils import T, sorted_dict_items
from .mapping_config import AllCircuitConfig, CircuitConfig, PhysicalRamConfig, RamConfig
from .logical_circuit import LogicalCircuit
from .siv_arch import SIVRamArch


def solve_all_circuits(ram_archs: Dict[int, SIVRamArch], logical_circuits: Dict[int, LogicalCircuit]) -> AllCircuitConfig:
    acc = AllCircuitConfig()
    for _, lc in sorted_dict_items(logical_circuits):
        acc.insert_circuit_config(solve_single_circuit(
            ram_archs=ram_archs, logical_circuit=lc))
    return acc


def solve_single_circuit(ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit) -> CircuitConfig:
    simple_circuit_solver = SimpleCircuitSolver(
        ram_archs=ram_archs, logical_circuit=logical_circuit)
    return simple_circuit_solver.solve()


def get_shape_fits(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape) -> List[(RamShapeFit)]:
    return [target_logical_shape.get_fit(smaller_shape=physical_shape) for physical_shape in candidate_physical_shapes]


def find_min_fit(candidate_physical_shapes: List[RamShape], target_logical_shape: RamShape, key_func: Callable[[RamShapeFit], T]) -> RamShape:
    fits = get_shape_fits(candidate_physical_shapes, target_logical_shape)
    return candidate_physical_shapes[min(enumerate(fits), key=lambda id_fit_pair:key_func(id_fit_pair[1]))[0]]


class SimpleCircuitSolver:
    def __init__(self, ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit):
        self._ram_archs = ram_archs
        self._logical_circuit = logical_circuit

    def solve_single_ram(self, ram_id: int) -> RamConfig:
        lr = self._logical_circuit.rams[ram_id]

        candidate_ram_arch_id_and_physical_shape = list()
        for ram_arch_id, ram_arch in sorted_dict_items(self._ram_archs):
            physical_shapes = ram_arch.get_shapes_for_mode(lr.mode)
            min_fit_physical_shape = find_min_fit(
                physical_shapes, lr.shape, key_func=lambda fit: (fit.get_count(), fit.num_series))
            candidate_ram_arch_id_and_physical_shape.append(
                (ram_arch_id, min_fit_physical_shape))
            min_serial_physical_shape = find_min_fit(
                physical_shapes, lr.shape, key_func=lambda fit: (fit.num_series, fit.get_count()))
            candidate_ram_arch_id_and_physical_shape.append(
                (ram_arch_id, min_serial_physical_shape))

        for ram_arch_id, physical_shape in candidate_ram_arch_id_and_physical_shape:
            prc = PhysicalRamConfig(
                id=0,
                physical_shape_fit=lr.shape.get_fit(
                    smaller_shape=physical_shape),
                ram_arch_id=ram_arch_id,
                ram_mode=lr.mode,
                physical_shape=physical_shape)

        return RamConfig(circuit_id=self._logical_circuit.circuit_id, ram_id=ram_id, lrc=None)

    def solve(self) -> CircuitConfig:
        cc = CircuitConfig(circuit_id=self._logical_circuit.circuit_id)
        for ram_id, _ in sorted_dict_items(self._logical_circuit.rams):
            cc.insert_ram_config(self.solve_single_ram(ram_id))
        return cc
