
from collections import OrderedDict
import logging
from typing import Dict, Iterator, NamedTuple, Tuple

from .utils import make_sorted_1d_dict

from .logical_ram import LogicalRam


class LogicalCircuit(NamedTuple):
    rams: Dict[int, LogicalRam]
    num_logic_blocks: int

    def sorted_rams_item(self) -> Iterator:
        return sorted(self.rams.items())


def parse_LogicBlock(lines_iter: Iterator[str]) -> OrderedDict[int, int]:
    # line 0: Circuit	"# Logic blocks (N=10, k=6, fracturable)"
    first_line = None
    while True:
        first_line = next(lines_iter).strip()
        if first_line != '':
            break
    assert first_line is not None

    logging.debug('After parsing:')
    logging.debug(f'  first_line={first_line}')

    def from_str(line: str) -> Tuple[int, int]:
        # 0	2941
        try:
            circuit_id_str, logic_block_count_str = line.split()
            return (int(circuit_id_str), int(logic_block_count_str))
        except ValueError:
            logging.error(
                f'Invalid str to parse for LogicBlock: {line}')
            raise
    # Rest of lines
    logical_blocks = [from_str(line.strip())
                      for line in lines_iter if line.strip() != '']
    logging.debug(f'  len(logical_blocks)={len(logical_blocks)}')

    # Sort by key
    lb_by_circuitid = make_sorted_1d_dict(dict(logical_blocks))

    logging.debug('After grouping:')
    logging.debug(f'  num_circuits={len(lb_by_circuitid)}')

    return lb_by_circuitid


def read_LogicBlock_from_file(filename: str) -> OrderedDict[int, int]:
    with open(filename, 'r') as f:
        return parse_LogicBlock(iter(f.readline, ''))
