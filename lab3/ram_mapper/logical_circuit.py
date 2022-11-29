
from collections import OrderedDict
from typing import Dict, Iterator, NamedTuple, Tuple

from .utils import make_sorted_1d_dict
from .logger import logger

from .logical_ram import LogicalRam, read_grouped_LogicalRam_from_file


class LogicalCircuit(NamedTuple):
    circuit_id: int
    rams: Dict[int, LogicalRam]
    num_logic_blocks: int


def parse_LogicBlock(lines_iter: Iterator[str]) -> OrderedDict[int, int]:
    # line 0: Circuit	"# Logic blocks (N=10, k=6, fracturable)"
    first_line = None
    while True:
        first_line = next(lines_iter).strip()
        if first_line != '':
            break
    assert first_line is not None

    logger.debug('parse_LogicBlock')
    logger.debug(f'  first_line={first_line}')

    def from_str(line: str) -> Tuple[int, int]:
        # 0	2941
        try:
            circuit_id_str, logic_block_count_str = line.split()
            return (int(circuit_id_str), int(logic_block_count_str))
        except ValueError:
            logger.error(
                f'Invalid str to parse for LogicBlock: {line}')
            raise
    # Rest of lines
    logical_blocks = [from_str(line.strip())
                      for line in lines_iter if line.strip() != '']
    logger.debug(f'  len(logical_blocks)={len(logical_blocks)}')

    # Sort by key
    lb_by_circuitid = make_sorted_1d_dict(dict(logical_blocks))

    logger.debug(f'  num_circuits(After grouping)={len(lb_by_circuitid)}')

    return lb_by_circuitid


def read_LogicBlock_from_file(filename: str) -> OrderedDict[int, int]:
    logger.info(f'Reading from {filename}')
    with open(filename, 'r') as f:
        return parse_LogicBlock(iter(f.readline, ''))


def merge_grouped_LogicalCircuit(logic_blocks: OrderedDict[int, int], logical_rams: OrderedDict[int, OrderedDict[int, LogicalRam]]) -> Dict[int, LogicalCircuit]:
    assert logic_blocks.keys() == logical_rams.keys()
    result = {circuit_id: LogicalCircuit(
        circuit_id=circuit_id, rams=logical_rams[circuit_id], num_logic_blocks=logic_blocks[circuit_id]) for circuit_id in logic_blocks.keys()}
    return result


def read_LogicalCircuit_from_file(logicblock_filename: str, loigicalram_filename: str) -> Dict[int, LogicalCircuit]:
    return merge_grouped_LogicalCircuit(logic_blocks=read_LogicBlock_from_file(logicblock_filename),
                                        logical_rams=read_grouped_LogicalRam_from_file(loigicalram_filename))
