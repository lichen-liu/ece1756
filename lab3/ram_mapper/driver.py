import logging

from .utils import sorted_dict_items

from . import siv_heuristics
from . import transform
from . import logical_circuit
from . import siv_arch


def init(parser):
    parser.add_argument(
        '--lb', type=str,
        default='logic_block_count.txt',
        help='Input logic_block_count.txt file')
    parser.add_argument(
        '--lr', type=str,
        default='logical_rams.txt',
        help='Input logical_rams.txt')
    parser.add_argument(
        '--out', type=str,
        default='mapping.txt',
        help='Output mapping.txt')
    parser.add_argument(
        '--no_area_report',
        action='store_true',
        help='Disable area report')


# python3 -m ram_mapper --lb=test0/logic_block_count.txt --lr=test0/logical_rams.txt --out=test0/mapping.txt
def run(args):
    logging.warning(f'{args}')
    logic_block_count_filename = args.lb
    logical_rams_filename = args.lr
    mapping_filename = args.out

    # Logical input
    lcs = logical_circuit.read_LogicalCircuit_from_file(
        logicblock_filename=logic_block_count_filename, loigicalram_filename=logical_rams_filename)

    # Arch input
    ram_archs = siv_arch.generate_default_ram_arch()
    logging.info('RAM Archs:')
    for ram_arch in ram_archs:
        logging.info(ram_arch)

    # Mapping output
    acc = transform.solve_all_circuits(
        ram_archs=ram_archs, logical_circuits=lcs)
    assert len(acc.circuits) == len(
        lcs), 'Final mapping result must contain same number of circuits as logical_ram input'
    acc.serialize_to_file(mapping_filename)

    if not args.no_area_report:
        logging.warning('=================')
        logging.warning('Final Area Report')
        # Print area
        for circuit_id, cc in sorted_dict_items(acc.circuits):
            siv_heuristics.calculate_fpga_area_for_circuit(
                ram_archs=ram_archs, logical_circuit=lcs[circuit_id], circuit_config=cc, verbose=True)
        logging.warning('=================')
