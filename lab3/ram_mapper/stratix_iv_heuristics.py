from collections import Counter
import logging
from typing import List
import math

from .physical_arch import RamType

from .utils import sorted_dict_items

from .stratix_iv_arch import RegularLogicBlockArch, SIVRamArch


def calculate_fpga_area(ram_arch: List[SIVRamArch], logic_block_count: int, extra_lut_count: int, physical_ram_count: Counter[int]) -> int:
    lb_arch = RegularLogicBlockArch()

    # Convert extra_lut_count + logic_block_count into regular_lb_used
    lb_to_lut_ratio = lb_arch.get_ratio_to_LUT()
    lb_for_extra_lut = math.ceil(
        extra_lut_count * lb_to_lut_ratio[0] / lb_to_lut_ratio[1])
    regular_lb_used = lb_for_extra_lut + logic_block_count

    logging.warning('')
    logging.warning(
        f'extra_lut_count={extra_lut_count} logic_block_for_extra_lut={lb_for_extra_lut}')
    logging.warning(f'regular_lb_used={regular_lb_used}')

    # Find logic block required for aspect ratio of RAM type
    lb_required = regular_lb_used
    num_lutram_block = 0
    for ram_arch_id, ram_count in sorted_dict_items(physical_ram_count):
        lb_to_ram_ratio = ram_arch[ram_arch_id].get_ratio_of_LB()
        min_lb_required = math.ceil(
            ram_count * lb_to_ram_ratio[0]/lb_to_ram_ratio[1])
        logging.warning(
            f'{ram_count}--{ram_arch[ram_arch_id]} requires {min_lb_required} LB')
        lb_required = max(lb_required, min_lb_required)
        if ram_arch[ram_arch_id].get_ram_type() == RamType.LUTRAM:
            num_lutram_block += ram_count
    logging.warning(f'FPGA architecture needs at least {lb_required} LB')

    # Add LUTRAM to logic block required
    lb_required_on_chip = lb_required + num_lutram_block
    logging.warning(
        f'FPGA architecture and logic circuit needs at least {lb_required_on_chip} LB')

    # Determine FPGA area
    fpga_area = 0
    for arch in [lb_arch] + ram_arch:
        lb_to_block_ratio = arch.get_ratio_of_LB()
        chip_block_count = math.floor(
            lb_required_on_chip / lb_to_block_ratio[0] * lb_to_block_ratio[1])
        block_area = chip_block_count * arch.get_area()
        logging.warning(f'{chip_block_count}--{arch} has area of {block_area}')
        fpga_area += block_area

    logging.warning(f'FPGA area is {fpga_area}')
    return fpga_area
