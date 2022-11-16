from abc import abstractmethod
from typing import List, Tuple
from ram_mapper import utils
from ram_mapper.logical_ram import RamMode
from ram_mapper.physical_ram import RamArch, RamType, RamShape


class SIVRamArch(RamArch):
    def __init__(self, id: int):
        super().__init__(id)

    @abstractmethod
    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        assert mode in RamMode
        assert mode in self.get_supported_mode()
        return []


class BlockRamArch(SIVRamArch):
    def __init__(self, id: int, max_width_shape: RamShape, ratio_of_LB: Tuple[int, int]):
        super().__init__(id)
        self._max_width_shape = max_width_shape
        self._ratio_of_LB = ratio_of_LB

    def get_ram_type(self) -> RamType:
        return RamType.BLOCK_RAM

    def get_supported_mode(self) -> RamMode:
        return RamMode.ROM | RamMode.SinglePort | RamMode.SimpleDualPort | RamMode.TrueDualPort

    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        super().get_shapes_for_mode(mode)
        max_width = self.get_max_width().width
        mode_max_width = max_width - 1 if mode == RamMode.TrueDualPort else max_width
        return [RamShape.from_size(self.get_size(), w) for w in utils.all_pow2_below(mode_max_width)]

    def get_max_width(self) -> RamShape:
        return self._max_width_shape

    def get_ratio_of_LB(self) -> Tuple[int, int]:
        return self._ratio_of_LB


class LUTRamArch(SIVRamArch):
    def __init__(self, id: int, ratio_of_LB: Tuple[int, int]):
        super().__init__(id)
        self._ratio_of_LB = ratio_of_LB

    def get_ram_type(self) -> RamType:
        return RamType.LUTRAM

    def get_supported_mode(self) -> RamMode:
        return RamMode.ROM | RamMode.SinglePort | RamMode.SimpleDualPort

    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        super().get_shapes_for_mode(mode)
        return [RamShape(20, 32), RamShape(10, 64)]

    def get_max_width(self) -> RamShape:
        return RamShape(20, 32)

    def get_ratio_of_LB(self) -> Tuple[int, int]:
        return self._ratio_of_LB


def create_from_str(id: int, checker_str: str) -> SIVRamArch:
    splitted = checker_str.lower().split()
    if RamType.BLOCK_RAM.value.lower() in splitted[0]:
        sz, mw, lb, br = splitted[1:]
        return BlockRamArch(id,
                            RamShape.from_size(int(sz), int(mw)),
                            (int(lb), int(br)))

    if RamType.LUTRAM.value.lower() in splitted[0]:
        lb, lr = splitted[1:]
        return LUTRamArch(id, (int(lb), int(lr)))

    raise Exception('Unrecognized checker_str RamType')


def create_all_from_strs(checker_strs: List[str]) -> List[SIVRamArch]:
    return [create_from_str(id, checker_str) for id, checker_str in enumerate(checker_strs)]


def create_all_from_str(raw_checker_str: str) -> List[SIVRamArch]:
    return create_all_from_strs(list(filter(len, raw_checker_str.split('-'))))
