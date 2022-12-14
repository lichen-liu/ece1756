from abc import ABC, abstractmethod
from enum import Enum
import math
from typing import List, Tuple
from .logical_ram import RamMode, RamShape


class RamType(Enum):
    LUTRAM = 'l'
    BLOCK_RAM = 'b'


class ArchProperty(ABC):
    @abstractmethod
    def get_area(self) -> int:
        pass

    @abstractmethod
    def get_ratio_of_LB(self) -> Tuple[int, int]:
        '''
        Ratio of logic blocks to current block type
        '''
        pass

    def get_block_count(self, LB_count: int) -> int:
        lb_to_block_ratio = self.get_ratio_of_LB()
        return math.floor(LB_count / lb_to_block_ratio[0] * lb_to_block_ratio[1])

    def __str__(self):
        ratio_of_lb_str = str(self.get_ratio_of_LB()).replace(' ', '')
        return f'LB:self{ratio_of_lb_str} Area:{self.get_area()}'

    def __eq__(self, other):
        return type(self) == type(other) and self.__dict__ == other.__dict__


class RamArchProperty(ArchProperty):
    '''
    A pure base to represent RAM architecture properties.
    Only universal assumptions are made
    '''
    @abstractmethod
    def get_ram_type(self) -> RamType:
        pass

    def get_size(self) -> int:
        return self.get_max_width().get_size()

    @abstractmethod
    def get_max_width(self) -> RamShape:
        pass

    @abstractmethod
    def get_supported_mode(self) -> RamMode:
        pass

    @abstractmethod
    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        pass

    def __str__(self):
        return f'{self.get_ram_type().name} {self.get_max_width()} ({self.get_supported_mode()}) {super().__str__()}'


class RamArch(RamArchProperty):
    '''
    With bookkeeping facilities
    '''

    def __init__(self, id: int):
        self._id = id

    def get_id(self) -> int:
        return self._id

    def __str__(self):
        return f'<{self.get_id()} {super().__str__()}>'
