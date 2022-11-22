
from typing import Dict, Iterator, NamedTuple

from .logical_ram import LogicalRam


class LogicalCircuit(NamedTuple):
    rams: Dict[int, LogicalRam]
    num_logic_blocks: int

    def sorted_rams_item(self) -> Iterator:
        return sorted(self.rams.items())
