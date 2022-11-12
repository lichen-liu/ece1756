from typing import NamedTuple
from enum import Flag, auto


class RamMode(Flag):
    ROM = auto()  # R
    SinglePort = auto()  # R/W
    SimpleDualPort = auto()  # R + W
    TrueDualPort = auto()  # R/W + R/W


class LogicalRam(NamedTuple):
    circuit_id: int
    ram_id: int
    mode: RamMode  # tmp, todo move into flag enum
    depth: int
    width: int
