from collections import defaultdict
import logging

from . import logical_circuit
from . import utils
from . import stratix_iv_ram
from . import mapping_config
from . import test_mapping_config


def run():
    # Logical input
    logic_block_count_filename = 'logic_block_count.txt'
    logical_rams_filename = 'logical_rams.txt'
    logical_circuit.read_LogicCircuit_from_file(
        logicblock_filename=logic_block_count_filename, loigicalram_filename=logical_rams_filename)
   
    # Arch input
    ramarchs = stratix_iv_ram.create_all_from_str(
        '-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1')
    logging.info('RAM Archs:')
    for ramarch in ramarchs:
        logging.info(ramarch)
    
    # Mapping output
    crc_by_circuitid_by_ramid = defaultdict(
        lambda: defaultdict(mapping_config.CircuitRamConfig))
    crc_list = [
        test_mapping_config.MappingConfigTestCase.generate_simple_CircuitRamConfig(),
        test_mapping_config.MappingConfigTestCase.generate_2level_CircuitRamConfig(),
        test_mapping_config.MappingConfigTestCase.generate_3level_CircuitRamConfig()]
    for crc in crc_list:
        crc_by_circuitid_by_ramid[crc.circuit_id][crc.ram_id] = crc
    crc_by_circuitid_by_ramid = utils.make_sorted_2d_dict(
        crc_by_circuitid_by_ramid)
    mapping_config.write_grouped_CircuitRamConfig_to_file(
        grouped_crc=crc_by_circuitid_by_ramid, filename='mapping.txt')
