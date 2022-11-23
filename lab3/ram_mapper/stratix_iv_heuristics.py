from typing import List

from .stratix_iv_arch import SIVRamArch
from .logical_circuit import LogicalCircuit
from .mapping_config import CircuitConfig


def calculate_fpga_area(ram_arch: List[SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig) -> int:
    pass
