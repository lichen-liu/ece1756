from abc import ABC, abstractmethod
from enum import Enum
from typing import Tuple


class RamType(Enum):
    LUTRAM = 'l'
    BLOCK_RAM = 'b'


# Done
class RamArchBase(ABC):
    '''
    A pure base to represent RAM architecture constants.
    Only universal assumptions are made?
    '''
    @abstractmethod
    def get_ram_type(self) -> RamType:
        pass

    @abstractmethod
    def get_size(self) -> int:
        pass

    @abstractmethod
    def get_max_width(self) -> int:
        pass

    @abstractmethod
    def get_ratio_of_LB(self) -> Tuple[int, int]:
        '''
        Ratio of logic blocks to RAM
        '''
        pass
