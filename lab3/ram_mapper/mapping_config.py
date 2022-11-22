from __future__ import annotations
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, Optional
from ram_mapper.physical_ram import RamShape
from ram_mapper.utils import Result
from ram_mapper.logical_ram import RamMode
from ram_mapper.stratix_iv_ram import determine_extra_luts


class ConfigVerifier(ABC):
    @abstractmethod
    def verify(self) -> Result:
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


class ConfigShape(ABC):
    @abstractmethod
    def get_shape(self) -> RamShape:
        pass


@dataclass
class CircuitRamConfig(ConfigVerifier, ConfigSerializer, ConfigShape):
    circuit_id: int
    ram_id: int
    num_extra_lut: int
    lrc: LogicalRamConfig

    def verify(self) -> Result:
        return self.lrc.verify()

    def serialize(self, level: int) -> str:
        return f'{self.circuit_id} {self.ram_id} {self.num_extra_lut} {self.lrc.serialize(level)}'

    def get_shape(self) -> RamShape:
        return self.lrc.get_shape()

    def update_extra_luts(self,  usage_mode: RamMode) -> int:
        '''
        Updates num_extra_lut and return
        '''
        self.num_extra_lut = self.lrc.get_extra_luts(usage_mode=usage_mode)
        return self.num_extra_lut


@dataclass
class LogicalRamConfig(ConfigVerifier, ConfigSerializer, ConfigShape):
    logical_width: int
    logical_depth: int
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
        self_str = f'LW {self.logical_width} LD {self.logical_depth}'
        child_str = self.prc.serialize(
            level) if self.prc is not None else self.clrc.serialize(level)
        return self_str + ' ' + child_str

    def get_shape(self) -> RamShape:
        return RamShape(width=self.logical_width, depth=self.logical_depth)

    def get_extra_luts(self, usage_mode: RamMode) -> int:
        if self.prc is not None:
            return determine_extra_luts(num_series=self.prc.num_series,
                                        logical_w=self.logical_width, ram_mode=usage_mode)
        else:
            lrc_l_extra_luts = self.clrc.lrc_l.get_extra_luts(
                usage_mode=usage_mode)
            lrc_r_extra_luts = self.clrc.lrc_r.get_extra_luts(
                usage_mode=usage_mode)
            clrc_extra_luts = 0
            if self.clrc.split == RamSplitDimension.series:
                clrc_extra_luts = determine_extra_luts(
                    num_series=2, logical_w=self.logical_width, ram_mode=usage_mode)
            return lrc_l_extra_luts + lrc_r_extra_luts + clrc_extra_luts


class RamSplitDimension(Enum):
    series = auto()
    parallel = auto()


@dataclass
class CombinedLogicalRamConfig(ConfigVerifier, ConfigSerializer, ConfigShape):
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


@dataclass
class PhysicalRamConfig(ConfigVerifier, ConfigSerializer, ConfigShape):
    id: int
    num_series: int
    num_parallel: int
    ram_arch_id: int
    ram_mode: RamMode
    width: int
    depth: int

    def verify(self) -> Result:
        return Result.good()

    def serialize(self, level: int) -> str:
        return f'ID {self.id} S {self.num_series} P {self.num_parallel} Type {self.ram_arch_id} Mode {self.ram_mode.name} W {self.width} D {self.depth}'

    def get_shape(self) -> RamShape:
        return RamShape(width=self.num_parallel*self.width, depth=self.num_series * self.depth)


def print_grouped_CircuitRamConfig(grouped_crc: OrderedDict[int, OrderedDict[int, CircuitRamConfig]]) -> Iterator[str]:
    for circuit_id, circuit_mapping in grouped_crc.items():
        for logical_ram_id, crc in circuit_mapping.items():
            result_str = f'// Circuit={circuit_id} Ram={logical_ram_id}\n'
            result_str += crc.serialize(level=0)
            result_str += '\n'
            yield result_str


def write_grouped_CircuitRamConfig_to_file(grouped_crc: OrderedDict[int, OrderedDict[int, CircuitRamConfig]], filename: str):
    with open(filename, mode='w')as f:
        f.writelines(print_grouped_CircuitRamConfig(grouped_crc=grouped_crc))
