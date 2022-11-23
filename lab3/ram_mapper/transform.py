from typing import Dict

from .utils import sorted_dict_items

from .mapping_config import AllCircuitConfig, CircuitConfig
from .logical_circuit import LogicalCircuit
from .siv_arch import SIVRamArch


def solve_all_circuits(ram_archs: Dict[int, SIVRamArch], logical_circuits: Dict[int, LogicalCircuit]) -> AllCircuitConfig:
    acc = AllCircuitConfig()
    for _, lc in sorted_dict_items(logical_circuits):
        acc.insert_circuit_config(solve_single_circuit(
            ram_archs=ram_archs, logical_circuit=lc))
    return acc


def solve_single_circuit(ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit) -> CircuitConfig:
    cc = CircuitConfig(circuit_id=logical_circuit.circuit_id)
    return cc
