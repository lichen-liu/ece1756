from typing import NamedTuple, TypeVar, Type
from enum import Flag, auto


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
