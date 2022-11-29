import itertools
import logging
import os
import statistics
from typing import Iterable, List

from . import utils
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
        '--report_circuit',
        nargs='+',
        type=int,
        default=[],
        help='Report QoR for circuit(s), -1 to print all')
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='Raise logging verbosity, default is Warning+')
    parser.add_argument(
        '--processes', '-j',
        type=int,
        default=os.cpu_count(),
        help=f'The number of processes for parallelism, default is {os.cpu_count()}'
    )
    parser.add_argument(
        '--circuits', '-c',
        type=int,
        default=None,
        help='The max number of circuits to process, default is all'
    )
    parser.add_argument(
        '--arch',
        type=str,
        default=siv_arch.DEFAULT_RAM_ARCH_STR,
        help='Architecture descrption string'
    )


def main(args):
    utils.proccess_initializer(args)

    logging.warning(f'{args}')

    with utils.elapsed_timer() as elapsed:
        run(args)
    logging.warning(f'Total elapsed {elapsed():.3f} seconds')


def geomean_fpga_area(fpga_area_list: Iterable[int]) -> float:
    factor = 10000000.0
    fpga_area_list_scaled_down = map(
        lambda area: float(area)/factor, fpga_area_list)
    geomean_scaled_down = statistics.geometric_mean(fpga_area_list_scaled_down)
    geomean = geomean_scaled_down * factor
    return geomean


# python3 -m ram_mapper --lb=test0/logic_block_count.txt --lr=test0/logical_rams.txt --out=test0/mapping.txt

def run(args):
    logic_block_count_filename = args.lb
    logical_rams_filename = args.lr
    mapping_filename = args.out

    # Logical input
    lcs = logical_circuit.read_LogicalCircuit_from_file(
        logicblock_filename=logic_block_count_filename, loigicalram_filename=logical_rams_filename)

    if args.circuits is not None and args.circuits < len(lcs):
        assert args.circuits > 0
        lcs = dict(itertools.islice(
            utils.sorted_dict_items(lcs), args.circuits))

    # Arch input
    archs = siv_arch.SIVArch.from_str(raw_checker_str=args.arch)
    logging.warning('SIV Archs:')
    for _, ram_arch in utils.sorted_dict_items(archs.ram_archs):
        logging.warning(ram_arch)
    logging.warning(archs.lb_arch)

    # Mapping output
    acc = transform.solve_all_circuits(
        archs=archs, logical_circuits=lcs, args=args)
    assert len(acc.circuits) == len(
        lcs), 'Final mapping result must contain same number of circuits as logical_ram input'
    acc.serialize_to_file(mapping_filename)

    # Calculate FPGA QoR
    if len(args.report_circuit) > 0:
        logging.warning('=================')
        logging.warning('Final Area Report')
    print_report_circuit_for_all = -1 in args.report_circuit
    circuit_fpga_qor_list: List[siv_heuristics.CircuitQor] = list()
    for circuit_id, cc in utils.sorted_dict_items(acc.circuits):
        circuit_fpga_qor = siv_heuristics.calculate_fpga_qor_for_circuit(
            archs=archs,
            logical_circuit=lcs[circuit_id],
            circuit_config=cc,
            allow_sharing=True,
            skip_area=False,
            verbose=print_report_circuit_for_all or (circuit_id in args.report_circuit))
        circuit_fpga_qor_list.append(circuit_fpga_qor)
    if len(args.report_circuit) > 0:
        logging.warning('=================')

    logging.warning(f'{siv_heuristics.CircuitQor.banner()}')
    for qor in circuit_fpga_qor_list:
        logging.warning(f'{qor.serialize()}')

    # Calculate FPGA area geomean
    fpga_area_geomean = geomean_fpga_area(
        map(lambda qor: qor.fpga_area, circuit_fpga_qor_list))
    logging.warning(
        f'Geometric Average Area for {len(circuit_fpga_qor_list)} circuits: {fpga_area_geomean:.6E}')
