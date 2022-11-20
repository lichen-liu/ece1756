from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
from ram_mapper.utils import Result

from ram_mapper.logical_ram import RamMode


class ConfigVerifier(ABC):
    @abstractmethod
    def verify(self) -> Result:
        pass


class ConfigPrinter(ABC):
    @staticmethod
    def indent_str(level: int) -> str:
        '''
        1 level = 4 spaces
        '''
        return level * 4 * ' '

    @abstractmethod
    def print(self, level: int) -> str:
        pass


@dataclass
class CircuitRamConfig(ConfigVerifier, ConfigPrinter):
    circuit_id: int
    ram_id: int
    num_extra_lut: int
    lrc: LogicalRamConfig

    def verify(self) -> Result:
        return self.lrc.verify()

    def print(self, level: int) -> str:
        return f'{self.circuit_id} {self.ram_id} {self.num_extra_lut} {self.lrc.print(level)}'


@dataclass
class LogicalRamConfig(ConfigVerifier, ConfigPrinter):
    logical_width: int
    logical_depth: int
    clrc: Optional[CombinedLogicalRamConfig] = None
    prc: Optional[PhysicalRamConfig] = None

    def verify(self) -> Result:
        if not (r := Result.satisfies((self.clrc is None) != (
                self.prc is None), 'Requires mutually exclusive CombinedLogicalRamConfig or PhysicalRamConfig')):
            return r
        if self.clrc is not None:
            return self.clrc.verify()
        else:
            return self.prc.verify()

    def print(self, level: int) -> str:
        self_str = f'LW {self.logical_width} LD {self.logical_depth}'
        child_str = ' ' + \
            self.prc.print(
                level) if self.prc is not None else self.clrc.print(level)
        return self_str + child_str


class RamSplitDimension(Enum):
    series = auto()
    parallel = auto()


@dataclass
class CombinedLogicalRamConfig(ConfigVerifier, ConfigPrinter):
    split: RamSplitDimension
    lrc_l: LogicalRamConfig
    lrc_r: LogicalRamConfig

    def verify(self) -> Result:
        if not (r := self.lrc_l.verify()):
            return r
        return self.lrc_r.verify()

    def print(self, level: int) -> str:
        self_str = f' {self.split.name}'
        level += 1
        lrc_l_str = ConfigPrinter.indent_str(level) + self.lrc_l.print(level)
        lrc_r_str = ConfigPrinter.indent_str(level) + self.lrc_r.print(level)
        return f'{self_str}\n{lrc_l_str}\n{lrc_r_str}'


@dataclass
class PhysicalRamConfig(ConfigVerifier, ConfigPrinter):
    id: int
    num_series: int
    num_parallel: int
    ram_arch_id: int
    ram_mode: RamMode
    width: int
    depth: int

    def verify(self) -> Result:
        return Result.good()

    def print(self, level: int) -> str:
        return f'ID {self.id} S {self.num_series} P {self.num_parallel} Type {self.ram_arch_id} Mode {self.ram_mode.name} W {self.width} D {self.depth}'
