import logging
from ram_mapper import stratix_iv_ram
from ram_mapper import logical_ram


def run():
    logical_ram.read_grouped_LogicalRam_from_file('logical_rams.txt')

    ramarchs = stratix_iv_ram.create_all_from_str(
        '-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1')
    logging.info('RAM Archs:')
    for ramarch in ramarchs:
        logging.info(ramarch)
