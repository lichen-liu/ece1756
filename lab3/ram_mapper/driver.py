from collections import defaultdict
import logging
from ram_mapper import utils
from ram_mapper import stratix_iv_ram
from ram_mapper import logical_ram
from ram_mapper import mapping_config
from ram_mapper import test_mapping_config


def run():
    logical_ram.read_grouped_LogicalRam_from_file('logical_rams.txt')

    ramarchs = stratix_iv_ram.create_all_from_str(
        '-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1')
    logging.info('RAM Archs:')
    for ramarch in ramarchs:
        logging.info(ramarch)

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
