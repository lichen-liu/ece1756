from typing import Iterator, NamedTuple, OrderedDict, TypeVar, Type
from collections import OrderedDict
from enum import Flag, auto
import logging


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
        circuit_id_str, ram_id_str, mode_str, depth_str, width_str = logical_ram_as_str.split()
        return cls(
            circuit_id=int(circuit_id_str),
            ram_id=int(ram_id_str),
            mode=RamMode[mode_str],
            depth=int(depth_str),
            width=int(width_str))


def parse_grouped_logical_ram(lines_iter: Iterator) -> OrderedDict[OrderedDict[LogicalRam]]:
    # line 0: Num_Circuits 69
    first_line = next(lines_iter).rstrip()
    _, num_circuits_str = first_line.split()
    num_circuits = int(num_circuits_str)
    # line 1: Circuit	RamID	Mode		Depth	Width
    second_line = next(lines_iter).rstrip()
    # Rest of lines
    logical_rams = [LogicalRam.from_str(line.rstrip()) for line in lines_iter]
    # Debug prints
    logging.debug('After parsing:')
    logging.debug(f'  first_line={first_line}')
    logging.debug(f'  second_line={second_line}')
    logging.debug(f'  len(logical_rams)={len(logical_rams)}')
    logging.debug(f'  num_circuits={num_circuits}')


def read_grouped_logical_ram_from_file(filename: str) -> OrderedDict[OrderedDict[LogicalRam]]:
    with open(filename, 'r') as f:
        return parse_grouped_logical_ram(iter(f.readline, ''))
