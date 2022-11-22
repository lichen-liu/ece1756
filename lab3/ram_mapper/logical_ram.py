from typing import Iterator, NamedTuple, OrderedDict, TypeVar, Type
from collections import OrderedDict, defaultdict
from enum import Flag, auto
import logging

from .utils import make_sorted_2d_dict


class RamMode(Flag):
    ROM = auto()  # R
    SinglePort = auto()  # R/W
    SimpleDualPort = auto()  # R + W
    TrueDualPort = auto()  # R/W + R/W


# Create a generic variable that can be 'LogicalRam', or any subclass.
LogicalRamT = TypeVar('LogicalRamT', bound='LogicalRam')


class LogicalRam(NamedTuple):
    circuit_id: int
    ram_id: int
    mode: RamMode  # tmp, todo move into flag enum
    depth: int
    width: int

    @classmethod
    def from_str(cls: Type[LogicalRamT], logical_ram_as_str: str) -> LogicalRamT:
        '''
        logical_ram_as_str:
        "Circuit	RamID	Mode		Depth	Width"
        "0	0	SimpleDualPort	45	12"
        '''
        try:
            circuit_id_str, ram_id_str, mode_str, depth_str, width_str = logical_ram_as_str.split()
            return cls(
                circuit_id=int(circuit_id_str),
                ram_id=int(ram_id_str),
                mode=RamMode[mode_str],
                depth=int(depth_str),
                width=int(width_str))
        except ValueError:
            logging.error(
                f'Invalid str to parse for LogicalRam: {logical_ram_as_str}')
            raise


def parse_grouped_LogicalRam(lines_iter: Iterator[str]) -> OrderedDict[int, OrderedDict[int, LogicalRam]]:
    # line 0: Num_Circuits 69
    first_line = next(lines_iter).strip()
    _, num_circuits_str = first_line.split()
    num_circuits = int(num_circuits_str)
    # line 1: Circuit	RamID	Mode		Depth	Width
    second_line = next(lines_iter).strip()
    logging.debug('After parsing:')
    logging.debug(f'  first_line={first_line}')
    logging.debug(f'  num_circuits={num_circuits}')
    logging.debug(f'  second_line={second_line}')
    # Rest of lines
    logical_rams = [LogicalRam.from_str(line.strip())
                    for line in lines_iter if line.strip() != '']
    logging.debug(f'  len(logical_rams)={len(logical_rams)}')

    lr_by_circuitid_by_ramid = defaultdict(lambda: defaultdict(LogicalRam))
    for lr in logical_rams:
        lr_by_circuitid_by_ramid[lr.circuit_id][lr.ram_id] = lr

    # Sort by key
    lr_by_circuitid_by_ramid = make_sorted_2d_dict(lr_by_circuitid_by_ramid)
    logging.debug('After grouping:')
    logging.debug(f'  num_circuits={len(lr_by_circuitid_by_ramid)}')

    assert len(
        lr_by_circuitid_by_ramid) == num_circuits, 'The actual number of circuits found must match the header'

    return lr_by_circuitid_by_ramid


def read_grouped_LogicalRam_from_file(filename: str) -> OrderedDict[OrderedDict[LogicalRam]]:
    with open(filename, 'r') as f:
        return parse_grouped_LogicalRam(iter(f.readline, ''))
