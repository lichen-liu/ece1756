from collections import Counter
from dataclasses import dataclass, field
import logging
from typing import Dict, List, Optional
import math

from .logical_ram import RamMode

from .mapping_config import CircuitConfig, LogicalRamConfig, PhysicalRamConfig

from .logical_circuit import LogicalCircuit

from .physical_arch import ArchProperty, RamType

from .utils import sorted_dict_items

from .siv_arch import RegularLogicBlockArch, SIVRamArch


@dataclass
class CircuitQor:
    ram_type_count_list: Optional[List[int]]
    regular_logic_block_count: int
    required_logic_block_count: int
    fpga_area: int
    circuit_id: int = field(default_factory=lambda: -1)

    def serialize(self) -> str:
        assert self.ram_type_count_list is not None
        seq = (self.circuit_id, *self.ram_type_count_list,
               self.regular_logic_block_count, self.required_logic_block_count, self.fpga_area)
        return '\t\t'.join(map(lambda x: str(x), seq))

    @staticmethod
    def banner(num_types: int = 3) -> str:
        type_list = [('Type ' + str(idx+1)) for idx in range(num_types)]
        seq = ('Circuit', *type_list, 'Blocks', 'Tiles', 'Area')
        return '\t\t'.join(seq)


def calculate_fpga_qor(ram_archs: Dict[int, SIVRamArch], logic_block_count: int, extra_lut_count: int, physical_ram_count: Counter[int], skip_area: bool = False, verbose: bool = False) -> CircuitQor:
    lb_arch = RegularLogicBlockArch()

    # Convert extra_lut_count + logic_block_count into regular_lb_used
    lb_for_extra_lut = lb_arch.get_block_count_from_luts(extra_lut_count)
    regular_lb_used = logic_block_count+lb_for_extra_lut

    if verbose:
        logging.warning('-----BEGIN calculate_fpga_area BEGIN-----')
        logging.warning(
            f'Extra LUTs: {extra_lut_count} ({lb_for_extra_lut} LBs)')
        logging.warning(
            f'Regular LBs: {logic_block_count} + {lb_for_extra_lut} ({regular_lb_used} LBs)')

    # Find logic block required for aspect ratio of RAM type
    if verbose:
        logging.warning('Aspect Ratio:')
    lb_required = 0
    lutram_lb_used = 0
    for ram_arch_id, ram_count in sorted_dict_items(physical_ram_count):
        lb_to_ram_ratio = ram_archs[ram_arch_id].get_ratio_of_LB()
        min_lb_required = math.ceil(
            ram_count * lb_to_ram_ratio[0]/lb_to_ram_ratio[1])
        if verbose:
            logging.warning(
                f'  {ram_count} {ram_archs[ram_arch_id]} requires {min_lb_required} LBs')
        lb_required = max(lb_required, min_lb_required)
        if ram_archs[ram_arch_id].get_ram_type() == RamType.LUTRAM:
            lutram_lb_used += ram_count
    if verbose:
        logging.warning(f'LUTRAM LBs: {lutram_lb_used}')
        logging.warning(
            f'FPGA architecture needs at least {lb_required} LBs for aspect ratio')

    # Add LUTRAM to logic block required
    lb_required_on_chip = max(regular_lb_used + lutram_lb_used, lb_required)
    if verbose:
        logging.warning(
            f'FPGA architecture and logic circuit needs at least {lb_required_on_chip} LBs')

    # Determine FPGA area
    if verbose:
        logging.warning('FPGA Area:')

    fpga_area = 0
    ram_type_count_list = None
    if not skip_area:
        def calculate_block_area(arch: ArchProperty, total_lb_count: int) -> int:
            chip_block_count = arch.get_block_count(total_lb_count)
            block_area = chip_block_count * arch.get_area()
            if verbose:
                logging.warning(
                    f'  {chip_block_count} {arch} has area of {block_area}')
            return block_area
        ram_type_count_list = list()
        for arch_id, arch in sorted_dict_items(ram_archs):
            block_area = calculate_block_area(arch, lb_required_on_chip)
            fpga_area += block_area
            ram_type_count_list.append(physical_ram_count.get(arch_id, 0))
        fpga_area += calculate_block_area(lb_arch, lb_required_on_chip)
    else:
        if verbose:
            logging.warning('  Skipped')
        # If area calculation is skipped, use lb_required_on_chip to represent area (propotional)
        fpga_area = lb_required_on_chip

    if verbose:
        logging.warning(f'FPGA area is {fpga_area}')
        logging.warning('-----END calculate_fpga_area END-----')

    return CircuitQor(ram_type_count_list=ram_type_count_list, regular_logic_block_count=regular_lb_used, required_logic_block_count=lb_required_on_chip, fpga_area=fpga_area)


def calculate_fpga_qor_for_circuit(ram_archs: Dict[int, SIVRamArch], logical_circuit: LogicalCircuit, circuit_config: CircuitConfig, allow_sharing: bool, skip_area: bool = False, verbose: bool = False) -> CircuitQor:
    assert logical_circuit.circuit_id == circuit_config.circuit_id
    if verbose:
        logging.warning(f'| circuit_id={logical_circuit.circuit_id} |')

    physical_ram_count = circuit_config.get_unique_physical_ram_count(
    ) if allow_sharing else circuit_config.get_physical_ram_count()
    qor = calculate_fpga_qor(
        ram_archs=ram_archs,
        logic_block_count=logical_circuit.num_logic_blocks,
        extra_lut_count=circuit_config.get_extra_lut_count(),
        physical_ram_count=physical_ram_count,
        skip_area=skip_area,
        verbose=verbose)
    qor.circuit_id = logical_circuit.circuit_id
    return qor


def calculate_fpga_qor_for_ram_config(ram_archs: Dict[int, SIVRamArch], logic_block_count: int, logical_ram_config: LogicalRamConfig, ram_mode: RamMode, skip_area: bool = False, verbose: bool = False) -> CircuitQor:
    return calculate_fpga_qor(
        ram_archs=ram_archs,
        logic_block_count=logic_block_count,
        extra_lut_count=logical_ram_config.get_extra_lut_count(
            ram_mode=ram_mode),
        physical_ram_count=logical_ram_config.get_physical_ram_count(),
        skip_area=skip_area,
        verbose=verbose)


def calculate_ram_area(ram_archs: Dict[int, SIVRamArch], extra_lut_count: int, prc: Optional[PhysicalRamConfig]=None):
    lb_arch = RegularLogicBlockArch()

    extra_lb_count = lb_arch.get_block_count_from_luts(extra_lut_count)
    regular_lb_area = extra_lb_count * lb_arch.get_area()

    ram_area = 0
    if prc is not None:
        ram_count = prc.physical_shape_fit.get_count()
        ram_area = ram_count * ram_archs[prc.ram_arch_id].get_area()

    return regular_lb_area + ram_area
