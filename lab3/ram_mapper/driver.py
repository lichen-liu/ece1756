from collections import defaultdict
import logging

from . import logical_circuit
from . import stratix_iv_arch
from . import mapping_config
from . import test_mapping_config


def run():
    # Logical input
    logic_block_count_filename = 'logic_block_count.txt'
    logical_rams_filename = 'logical_rams.txt'
    logical_circuit.read_LogicCircuit_from_file(
        logicblock_filename=logic_block_count_filename, loigicalram_filename=logical_rams_filename)

    # Arch input
    ramarchs = stratix_iv_arch.generate_default_arch()
    logging.info('RAM Archs:')
    for ramarch in ramarchs:
        logging.info(ramarch)

    # Mapping output
    acc = mapping_config.AllCircuitConfig()
    rc_list = [
        test_mapping_config.MappingConfigTestCase.generate_1level_RamConfig(),
        test_mapping_config.MappingConfigTestCase.generate_2level_RamConfig(),
        test_mapping_config.MappingConfigTestCase.generate_3level_RamConfig()]
    for rc in rc_list:
        acc.insert_ram_config(rc)
    acc.serialize_to_file('mapping.txt')
