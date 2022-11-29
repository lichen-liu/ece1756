from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import chain
from typing import Callable, Dict, Iterator, List, Optional
from .physical_arch import RamShape
from .logger import logger
from .utils import list_add, list_set, sorted_dict_items
from .logical_ram import RamMode, RamShapeFit
from .siv_arch import accumulate_extra_luts, determine_extra_luts, determine_write_decoder_luts


class ConfigSerializer(ABC):
    @staticmethod
    def indent_str(level: int) -> str:
        '''
        1 level = 4 spaces
        '''
        return level * 4 * ' '

    @abstractmethod
    def serialize(self, level: int) -> str:
        pass

    def serialize_gen(self, level: int) -> Iterator[str]:
        '''
        By default, return an Iterator[str] of the lines-splitted self.serialize()
        '''
        return iter(self.serialize(level).splitlines())

    def serialize_to_file(self, filename: str):
        logger.info(f'Writing to {filename}')
        with open(filename, 'w') as f:
            f.writelines(self.serialize_gen(0))


class ConfigLeafExecutor(ABC):
    '''
    Find the LogicalRamConfig that has PhysicalRamConfig and call the callback function
    '''
    @abstractmethod
    def execute_on_leaf(self, callback: Callable[[LogicalRamConfig]]):
        pass


class ConfigShape(ABC):
    @abstractmethod
    def get_shape(self) -> RamShape:
        pass


class ConfigPhysicalRamCount(ABC):
    @abstractmethod
    def get_physical_ram_count(self) -> List[int]:
        '''
        {ram_arch_id: count}
        '''
        pass


class ConfigExtraLutCount(ABC):
    @abstractmethod
    def get_extra_lut_count(self) -> int:
        pass


@dataclass
class RamConfig(ConfigSerializer, ConfigShape, ConfigPhysicalRamCount, ConfigExtraLutCount, ConfigLeafExecutor):
    circuit_id: int
    ram_id: int
    lrc: LogicalRamConfig
    ram_mode: RamMode

    def serialize(self, level: int) -> str:
        return f'{self.circuit_id} {self.ram_id} {self.get_extra_lut_count()} {self.lrc.serialize(level)}'

    def get_shape(self) -> RamShape:
        return self.lrc.get_shape()

    def get_extra_lut_count(self) -> int:
        return self.lrc.get_extra_lut_count(self.ram_mode)

    def get_physical_ram_count(self) -> List[int]:
        return self.lrc.get_physical_ram_count()

    def execute_on_leaf(self, callback: Callable[[LogicalRamConfig]]):
        self.lrc.execute_on_leaf(callback)


@dataclass
class LogicalRamConfig(ConfigSerializer, ConfigShape, ConfigPhysicalRamCount, ConfigLeafExecutor):
    logical_shape: RamShape
    clrc: Optional[CombinedLogicalRamConfig] = None
    prc: Optional[PhysicalRamConfig] = None

    def serialize(self, level: int) -> str:
        self_str = f'LW {self.logical_shape.width} LD {self.logical_shape.depth}'
        child_str = self.prc.serialize(
            level) if self.prc is not None else self.clrc.serialize(level)
        return self_str + ' ' + child_str

    def get_shape(self) -> RamShape:
        return self.logical_shape

    def get_immediate_num_series(self) -> Optional[int]:
        if self.prc is not None:
            return self.prc.physical_shape_fit.num_series
        else:
            return None

    def get_extra_lut_count(self, ram_mode: RamMode) -> int:
        if self.prc is not None:
            return determine_extra_luts(num_series=self.prc.physical_shape_fit.num_series,
                                        logical_w=self.logical_shape.width, ram_mode=ram_mode)
        else:
            lrc_l_extra_luts = self.clrc.lrc_l.get_extra_lut_count(
                ram_mode=ram_mode)
            lrc_r_extra_luts = self.clrc.lrc_r.get_extra_lut_count(
                ram_mode=ram_mode)
            clrc_extra_luts = 0
            if self.clrc.split == RamSplitDimension.series:
                clrc_extra_luts = determine_extra_luts(
                    num_series=2, logical_w=self.logical_shape.width, ram_mode=ram_mode)
            else:
                # Remove the duplicated count of the write luts if they can be shared
                lrc_l_immediate_num_series = self.clrc.lrc_l.get_immediate_num_series()
                lrc_r_immediate_num_series = self.clrc.lrc_r.get_immediate_num_series()
                if lrc_l_immediate_num_series is not None and lrc_r_immediate_num_series is not None:
                    if lrc_l_immediate_num_series == lrc_r_immediate_num_series:
                        write_luts = determine_write_decoder_luts(
                            r=lrc_l_immediate_num_series)
                        clrc_extra_luts = -accumulate_extra_luts(
                            write_luts=write_luts, read_luts=0, ram_mode=ram_mode)
            return lrc_l_extra_luts + lrc_r_extra_luts + clrc_extra_luts

    def get_physical_ram_count(self) -> List[int]:
        if self.prc is not None:
            return self.prc.get_physical_ram_count()
        else:
            return self.clrc.get_physical_ram_count()

    def execute_on_leaf(self, callback: Callable[[LogicalRamConfig]]):
        if self.prc is not None:
            callback(self)
        else:
            self.clrc.execute_on_leaf(callback)


class RamSplitDimension(Enum):
    series = auto()
    parallel = auto()


@dataclass
class CombinedLogicalRamConfig(ConfigSerializer, ConfigShape, ConfigPhysicalRamCount, ConfigLeafExecutor):
    split: RamSplitDimension
    lrc_l: LogicalRamConfig
    lrc_r: LogicalRamConfig

    def serialize(self, level: int) -> str:
        self_str = f'{self.split.name}'
        level += 1
        lrc_l_str = ConfigSerializer.indent_str(
            level) + self.lrc_l.serialize(level)
        lrc_r_str = ConfigSerializer.indent_str(
            level) + self.lrc_r.serialize(level)
        return f'{self_str}\n{lrc_l_str}\n{lrc_r_str}'

    def get_shape(self) -> RamShape:
        lrc_l_shape = self.lrc_l.get_shape()
        lrc_r_shape = self.lrc_r.get_shape()
        if self.split == RamSplitDimension.series:
            return RamShape(width=lrc_l_shape.width, depth=lrc_l_shape.depth+lrc_r_shape.depth)
        else:
            return RamShape(width=lrc_l_shape.width+lrc_r_shape.width, depth=lrc_l_shape.depth)

    def get_physical_ram_count(self) -> List[int]:
        return list_add(self.lrc_l.get_physical_ram_count(), self.lrc_r.get_physical_ram_count())

    def execute_on_leaf(self, callback: Callable[[LogicalRamConfig]]):
        self.lrc_l.execute_on_leaf(callback)
        self.lrc_r.execute_on_leaf(callback)


@dataclass
class PhysicalRamConfig(ConfigSerializer, ConfigShape, ConfigPhysicalRamCount):
    id: int
    physical_shape_fit: RamShapeFit
    ram_arch_id: int
    ram_mode: RamMode
    physical_shape: RamShape

    def serialize(self, level: int) -> str:
        return f'ID {self.id} S {self.physical_shape_fit.num_series} P {self.physical_shape_fit.num_parallel} Type {self.ram_arch_id} Mode {self.ram_mode.name} W {self.physical_shape.width} D {self.physical_shape.depth}'

    def get_shape(self) -> RamShape:
        return RamShape(width=self.physical_shape_fit.num_parallel*self.physical_shape.width, depth=self.physical_shape_fit.num_series * self.physical_shape.depth)

    def get_physical_ram_count(self) -> List[int]:
        l = [0] * (self.ram_arch_id + 1)
        l[self.ram_arch_id] = self.physical_shape_fit.get_count()
        return l


@dataclass
class CircuitConfig(ConfigSerializer, ConfigPhysicalRamCount, ConfigExtraLutCount, ConfigLeafExecutor):
    circuit_id: int
    rams: Dict[int, RamConfig] = field(default_factory=dict)

    def serialize_gen(self, level: int) -> Iterator[str]:
        for ram_id, crc in sorted_dict_items(self.rams):
            result_str = f'// Circuit={self.circuit_id} Ram={ram_id}\n'
            result_str += crc.serialize(level)
            result_str += '\n'
            yield result_str

    def serialize(self, level: int) -> str:
        return ''.join(self.serialize_gen(level))

    def insert_ram_config(self, rc: RamConfig):
        assert rc.circuit_id == self.circuit_id
        self.rams[rc.ram_id] = rc

    def get_physical_ram_count(self) -> List[int]:
        c = list()
        for ram in self.rams.values():
            c = list_add(c, ram.get_physical_ram_count())
        return c

    def get_unique_physical_ram_count(self) -> List[int]:
        uid_prc_dict: Dict[int, PhysicalRamConfig] = dict()

        def visitor(lrc: LogicalRamConfig):
            uid_prc_dict[lrc.prc.id] = lrc.prc
        self.execute_on_leaf(visitor)
        c = list()
        for prc in uid_prc_dict.values():
            c = list_add(c, prc.get_physical_ram_count())
        return c

    def get_extra_lut_count(self) -> int:
        return sum(map(lambda rc: rc.get_extra_lut_count(), self.rams.values()))

    def execute_on_leaf(self, callback: Callable[[LogicalRamConfig]]):
        for ram in self.rams.values():
            ram.execute_on_leaf(callback)


@dataclass
class AllCircuitConfig(ConfigSerializer):
    circuits: Dict[int, CircuitConfig] = field(default_factory=dict)

    def serialize_gen(self, level: int) -> Iterator[str]:
        banner_str = ConfigSerializer.indent_str(
            level) + f'// Num_Circuits {len(self.circuits)}\n'
        return chain(iter([banner_str]), chain.from_iterable((cc.serialize_gen(level) for _, cc in sorted_dict_items(self.circuits))))

    def serialize(self, level: int) -> str:
        return ''.join(self.serialize_gen(level))

    def insert_ram_config(self, rc: RamConfig):
        if rc.circuit_id not in self.circuits:
            self.circuits[rc.circuit_id] = CircuitConfig(
                circuit_id=rc.circuit_id)
        self.circuits[rc.circuit_id].insert_ram_config((rc))

    def insert_circuit_config(self, cc: CircuitConfig):
        self.circuits[cc.circuit_id] = cc
