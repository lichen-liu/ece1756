from collections import Counter
import logging
from typing import Dict, List
import math

from .mapping_config import CircuitConfig, LogicalRamConfig

from .logical_circuit import LogicalCircuit

from .physical_arch import RamType

from .utils import sorted_dict_items

from .siv_arch import RegularLogicBlockArch, SIVRamArch


def calculate_fpga_area(ram_arch: Dict[int, SIVRamArch], logic_block_count: int, extra_lut_count: int, physical_ram_count: Counter[int], verbose: bool = False) -> int:
    lb_arch = RegularLogicBlockArch()

    # Convert extra_lut_count + logic_block_count into regular_lb_used
    lb_to_lut_ratio = lb_arch.get_ratio_to_LUT()
    lb_for_extra_lut = math.ceil(
        extra_lut_count * lb_to_lut_ratio[0] / lb_to_lut_ratio[1])
    regular_lb_used = logic_block_count+lb_for_extra_lut

    if verbose:
        logging.warning('=====BEGIN calculate_fpga_area BEGIN=====')
        logging.warning(
            f'Extra LUTs: {extra_lut_count} ({lb_for_extra_lut} LBs)')
        logging.warning(
            f'Regular LBs: {logic_block_count} + {lb_for_extra_lut} ({regular_lb_used} LBs)')

    # Find logic block required for aspect ratio of RAM type
    if verbose:
        logging.warning('Aspect Ratio:')
    lb_required = regular_lb_used
    num_lutram_block = 0
    for ram_arch_id, ram_count in sorted_dict_items(physical_ram_count):
        lb_to_ram_ratio = ram_arch[ram_arch_id].get_ratio_of_LB()
        min_lb_required = math.ceil(
            ram_count * lb_to_ram_ratio[0]/lb_to_ram_ratio[1])
        if verbose:
            logging.warning(
                f'  {ram_count} {ram_arch[ram_arch_id]} requires {min_lb_required} LBs')
        lb_required = max(lb_required, min_lb_required)
        if ram_arch[ram_arch_id].get_ram_type() == RamType.LUTRAM:
            num_lutram_block += ram_count
    if verbose:
        logging.warning(
            f'FPGA architecture needs at least {lb_required} LBs for aspect ratio')

    # Add LUTRAM to logic block required
    lb_required_on_chip = lb_required + num_lutram_block
    if verbose:
        logging.warning(
            f'FPGA architecture and logic circuit needs at least {lb_required_on_chip} LBs')

    # Determine FPGA area
    if verbose:
        logging.warning('FPGA Area:')
    fpga_area = 0
    for arch in [lb_arch] + list(ram_arch.values()):
        lb_to_block_ratio = arch.get_ratio_of_LB()
        chip_block_count = math.floor(
            lb_required_on_chip / lb_to_block_ratio[0] * lb_to_block_ratio[1])
        block_area = chip_block_count * arch.get_area()
        if verbose:
            logging.warning(
                f'  {chip_block_count} {arch} has area of {block_area}')
        fpga_area += block_area

    if verbose:
        logging.warning(f'FPGA area is {fpga_area}')
        logging.warning('=====END calculate_fpga_area END=====')

    return fpga_area


def calculate_fpga_area_for_circuit(ram_arch: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, verbose: bool = False) -> int:
    assert logical_circuit.circuit_id == circuit_config.circuit_id
    if verbose:
        logging.warning(f'| circuit_id={logical_circuit.circuit_id} |')
    return calculate_fpga_area(
        ram_arch=ram_arch,
        logic_block_count=logical_circuit.num_logic_blocks,
        extra_lut_count=circuit_config.get_extra_lut_count(
            ram_modes=logical_circuit.get_ram_modes()),
        physical_ram_count=circuit_config.get_physical_ram_count(),
        verbose=verbose)


# def calculate_fpga_area_for_ram_config(ram_arch: Dict[int, SIVRamArch], logic_block_count: int, logical_ram_config: LogicalRamConfig, verbose: bool = False) -> int:
#     return calculate_fpga_area(
#         ram_arch=ram_arch,
#         logic_block_count=logic_block_count,
#         extra_lut_count=logical_ram_config.get_extra_luts(),
#         physical_ram_count=circuit_config.get_physical_ram_count(),
#         verbose=verbose)
