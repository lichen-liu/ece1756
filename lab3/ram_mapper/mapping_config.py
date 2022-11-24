from __future__ import annotations
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import chain
import logging
from typing import Dict, Iterator, Optional
from .physical_arch import RamShape
from .utils import Result, sorted_dict_items
from .logical_ram import RamMode, RamShapeFit
from .siv_arch import determine_extra_luts


class ConfigVerifier(ABC):
    @abstractmethod
    def verify(self) -> Result:
        pass


class ConfigRamMode(ABC):
    @abstractmethod
    def get_ram_mode(self) -> RamMode:
        pass


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
        logging.info(f'Writing to {filename}')
        with open(filename, 'w') as f:
            f.writelines(self.serialize_gen(0))


class ConfigShape(ABC):
    @abstractmethod
    def get_shape(self) -> RamShape:
        pass


class ConfigPhysicalRamCount(ABC):
    @abstractmethod
    def get_physical_ram_count(self) -> Counter[int]:
        '''
        {ram_arch_id: count}
        '''
        pass


class ConfigExtraLutCount(ABC):
    @abstractmethod
    def get_extra_lut_count(self) -> int:
        pass


@dataclass
class RamConfig(ConfigVerifier, ConfigSerializer, ConfigShape, ConfigPhysicalRamCount, ConfigRamMode, ConfigExtraLutCount):
    circuit_id: int
    ram_id: int
    lrc: LogicalRamConfig

    def verify(self) -> Result:
        return self.lrc.verify()

    def serialize(self, level: int) -> str:
        return f'{self.circuit_id} {self.ram_id} {self.get_extra_lut_count()} {self.lrc.serialize(level)}'

    def get_shape(self) -> RamShape:
        return self.lrc.get_shape()

    def get_extra_lut_count(self) -> int:
        return self.lrc.get_extra_lut_count()

    def get_physical_ram_count(self) -> Counter[int]:
        return self.lrc.get_physical_ram_count()

    def get_ram_mode(self) -> RamMode:
        return self.lrc.get_ram_mode()


@dataclass
class LogicalRamConfig(ConfigVerifier, ConfigSerializer, ConfigShape, ConfigPhysicalRamCount, ConfigRamMode, ConfigExtraLutCount):
    logical_shape: RamShape
    clrc: Optional[CombinedLogicalRamConfig] = None
    prc: Optional[PhysicalRamConfig] = None

    def verify(self) -> Result:
        if not (r := Result.expect((self.clrc is None) != (
                self.prc is None), 'Requires mutually exclusive CombinedLogicalRamConfig or PhysicalRamConfig')):
            return r
        if self.clrc is not None:
            if not (r := self.clrc.verify()):
                return r
            return Result.expect(self.clrc.get_shape() == self.get_shape(),
                                 'Requires the actual physical shape from CombinedLogicalRamConfig to match the expected logical shape')
        else:
            if not (r := self.prc.verify()):
                return r
            prc_shape = self.prc.get_shape()
            self_shape = self.get_shape()
            return Result.expect(prc_shape.width >= self_shape.width and prc_shape.depth >= self_shape.depth,
                                 'Requires the actual physical shape from PhysicalRamConfig to be not less than (both width and depth) the expected logical shape')

    def serialize(self, level: int) -> str:
        self_str = f'LW {self.logical_shape.width} LD {self.logical_shape.depth}'
        child_str = self.prc.serialize(
            level) if self.prc is not None else self.clrc.serialize(level)
        return self_str + ' ' + child_str

    def get_shape(self) -> RamShape:
        return self.logical_shape

    def get_extra_lut_count(self) -> int:
        if self.prc is not None:
            return determine_extra_luts(num_series=self.prc.physical_shape_fit.num_series,
                                        logical_w=self.logical_shape.width, ram_mode=self.get_ram_mode())
        else:
            lrc_l_extra_luts = self.clrc.lrc_l.get_extra_lut_count()
            lrc_r_extra_luts = self.clrc.lrc_r.get_extra_lut_count()
            clrc_extra_luts = 0
            if self.clrc.split == RamSplitDimension.series:
                clrc_extra_luts = determine_extra_luts(
                    num_series=2, logical_w=self.logical_shape.width, ram_mode=self.get_ram_mode())
            return lrc_l_extra_luts + lrc_r_extra_luts + clrc_extra_luts

    def get_physical_ram_count(self) -> Counter[int]:
        if self.prc is not None:
            return self.prc.get_physical_ram_count()
        else:
            return self.clrc.get_physical_ram_count()

    def get_ram_mode(self) -> RamMode:
        if self.prc is not None:
            return self.prc.get_ram_mode()
        else:
            return self.clrc.get_ram_mode()


class RamSplitDimension(Enum):
    series = auto()
    parallel = auto()


@dataclass
class CombinedLogicalRamConfig(ConfigVerifier, ConfigSerializer, ConfigShape, ConfigPhysicalRamCount, ConfigRamMode):
    split: RamSplitDimension
    lrc_l: LogicalRamConfig
    lrc_r: LogicalRamConfig

    def verify(self) -> Result:
        if not (r := self.lrc_l.verify()):
            return r
        if not (r := self.lrc_r.verify()):
            return r

        lrc_l_shape = self.lrc_l.get_shape()
        lrc_r_shape = self.lrc_r.get_shape()
        if self.split == RamSplitDimension.series:
            return Result.expect(lrc_l_shape.width == lrc_r_shape.width, 'Requires width to match in series mode')
        else:
            return Result.expect(lrc_l_shape.depth == lrc_r_shape.depth, 'Requires depth to match in parallel mode')

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

    def get_physical_ram_count(self) -> Counter[int]:
        return self.lrc_l.get_physical_ram_count() + self.lrc_r.get_physical_ram_count()

    def get_ram_mode(self) -> RamMode:
        lrc_l_ram_mode = self.lrc_l.get_ram_mode()
        lrc_r_ram_mode = self.lrc_r.get_ram_mode()
        assert lrc_l_ram_mode == lrc_r_ram_mode
        return lrc_l_ram_mode


@dataclass
class PhysicalRamConfig(ConfigVerifier, ConfigSerializer, ConfigShape, ConfigPhysicalRamCount, ConfigRamMode):
    id: int
    physical_shape_fit: RamShapeFit
    ram_arch_id: int
    ram_mode: RamMode
    physical_shape: RamShape

    def verify(self) -> Result:
        return Result.good()

    def serialize(self, level: int) -> str:
        return f'ID {self.id} S {self.physical_shape_fit.num_series} P {self.physical_shape_fit.num_parallel} Type {self.ram_arch_id} Mode {self.ram_mode.name} W {self.physical_shape.width} D {self.physical_shape.depth}'

    def get_shape(self) -> RamShape:
        return RamShape(width=self.physical_shape_fit.num_parallel*self.physical_shape.width, depth=self.physical_shape_fit.num_series * self.physical_shape.depth)

    def get_physical_ram_count(self) -> Counter[int]:
        return Counter({self.ram_arch_id: self.physical_shape_fit.num_parallel*self.physical_shape_fit.num_series})

    def get_ram_mode(self) -> RamMode:
        return self.ram_mode


@dataclass
class CircuitConfig(ConfigSerializer, ConfigPhysicalRamCount, ConfigExtraLutCount):
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

    def get_physical_ram_count(self) -> Counter[int]:
        c = Counter()
        for _, ram in sorted_dict_items(self.rams):
            c.update(ram.get_physical_ram_count())
        return c

    def get_extra_lut_count(self) -> int:
        return sum(map(lambda ram_id_rc: ram_id_rc[1].get_extra_lut_count(), sorted_dict_items(self.rams)))


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
