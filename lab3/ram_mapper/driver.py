from collections import defaultdict
import logging

from . import siv_heuristics
from . import transform
from . import logical_circuit
from . import siv_arch
from . import mapping_config
from . import test_mapping_config


def run():
    # Logical input
    logic_block_count_filename = 'logic_block_count.txt'
    logical_rams_filename = 'logical_rams.txt'
    lcs = logical_circuit.read_LogicCircuit_from_file(
        logicblock_filename=logic_block_count_filename, loigicalram_filename=logical_rams_filename)

    # Arch input
    ram_archs = siv_arch.generate_default_ram_arch()
    logging.info('RAM Archs:')
    for ram_arch in ram_archs:
        logging.info(ram_arch)

    # Mapping output
    acc = mapping_config.AllCircuitConfig()
    rc_list = [
        test_mapping_config.MappingConfigTestCase.generate_1level_RamConfig(),
        test_mapping_config.MappingConfigTestCase.generate_2level_RamConfig(),
        test_mapping_config.MappingConfigTestCase.generate_3level_RamConfig()]
    for rc in rc_list:
        acc.insert_ram_config(rc)
    acc.serialize_to_file('mapping.txt')

    # Print area
    siv_heuristics.calculate_fpga_area_for_circuit(
        ram_arch=ram_archs, logical_circuit=lcs[3], circuit_config=acc.circuits[3], verbose=True)
