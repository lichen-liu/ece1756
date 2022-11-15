from typing import List
from ram_mapper import utils
from ram_mapper.logical_ram import RamMode
from ram_mapper.physical_ram import RamArch, RamType, RamShape


class BlockRamArch(RamArch):
    def __init__(self, id: int):
        super().__init__(id)

    def get_ram_type(self) -> RamType:
        return RamType.BLOCK_RAM

    def get_supported_ram_mode(self) -> RamMode:
        return RamMode.ROM or RamMode.SinglePort or RamMode.SimpleDualPort or RamMode.TrueDualPort

    def get_shapes_for_ram_mode(self, mode: RamMode) -> List[RamShape]:
        assert len(mode) == 1
        assert mode in self.get_supported_ram_mode()
        if mode == RamMode.TrueDualPort:
            pass
        else:
            utils.all_pow2_below(self.get_max_width().width)


class LUTRamArch(RamArch):
    def __init__(self, id: int):
        super().__init__(id)

    def get_ram_type(self) -> RamType:
        return RamType.LUTRAM

    def get_supported_ram_mode(self) -> RamMode:
        return RamMode.ROM or RamMode.SinglePort or RamMode.SimpleDualPort
