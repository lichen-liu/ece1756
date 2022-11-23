from collections import Counter
from typing import Dict, List

from .stratix_iv_arch import SIVRamArch


def calculate_fpga_area(ram_arch: List[SIVRamArch], logic_block_count: int, extra_lut_count: int, physical_ram_count: Counter[int]) -> int:
    pass
