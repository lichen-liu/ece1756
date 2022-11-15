from abc import ABC, abstractmethod
from enum import Enum
from typing import List, NamedTuple, Tuple, Type, TypeVar
from ram_mapper.logical_ram import RamMode


class RamType(Enum):
    LUTRAM = 'l'
    BLOCK_RAM = 'b'


# Create a generic variable that can be 'LogicalRam', or any subclass.
RamShapeT = TypeVar('RamShapeT', bound='RamShape')


class RamShape(NamedTuple):
    width: int
    depth: int

    def get_size(self) -> int:
        return self.width * self.depth

    @classmethod
    def from_size_width(cls: Type[RamShapeT], size: int, width: int) -> RamShapeT:
        pass


class RamArchProperty(ABC):
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
    def get_ratio_of_LB(self) -> Tuple[int, int]:
        '''
        Ratio of logic blocks to RAM
        '''
        pass

    @abstractmethod
    def get_supported_ram_mode(self) -> RamMode:
        pass

    @abstractmethod
    def get_shapes_for_ram_mode(self, mode: RamMode) -> List[RamShape]:
        pass


class RamArch(RamArchProperty):
    '''
    With bookkeeping facilities
    '''

    def __init__(self, id: int):
        self._id = id

    def get_id(self) -> int:
        return self._id
