from typing import List, Tuple
from ram_mapper import utils
from ram_mapper.logical_ram import RamMode
from ram_mapper.physical_ram import RamArch, RamType, RamShape


class BlockRamArch(RamArch):
    def __init__(self, id: int):
        super().__init__(id)

    def get_ram_type(self) -> RamType:
        return RamType.BLOCK_RAM

    def get_supported_mode(self) -> RamMode:
        return RamMode.ROM | RamMode.SinglePort | RamMode.SimpleDualPort | RamMode.TrueDualPort

    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        assert mode in RamMode
        assert mode in self.get_supported_mode()
        max_width = self.get_max_width().width
        mode_max_width = max_width - 1 if mode == RamMode.TrueDualPort else max_width
        return [RamShape.from_size(self.get_size(), w) for w in utils.all_pow2_below(mode_max_width)]


class ConcreteBlockRamArch(BlockRamArch):
    def __init__(self, id: int, max_width_shape: RamShape, ratio_of_LB: Tuple[int, int]):
        super().__init__(id)
        self._max_width_shape = max_width_shape
        self._ratio_of_LB = ratio_of_LB

    def get_max_width(self) -> RamShape:
        return self._max_width_shape

    def get_ratio_of_LB(self) -> Tuple[int, int]:
        return self._ratio_of_LB


class LUTRamArch(RamArch):
    def __init__(self, id: int):
        super().__init__(id)

    def get_ram_type(self) -> RamType:
        return RamType.LUTRAM

    def get_supported_mode(self) -> RamMode:
        return RamMode.ROM or RamMode.SinglePort or RamMode.SimpleDualPort
