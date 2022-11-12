from typing import NamedTuple


class LogicalRam(NamedTuple):
    circuit_id: int
    ram_id: int
    mode: str  # tmp, todo move into flag enum
    depth: int
    width: int
