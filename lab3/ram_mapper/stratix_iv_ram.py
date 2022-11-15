from ram_mapper.logical_ram import RamMode
from ram_mapper.physical_ram import RamArch, RamType


class BlockRamArch(RamArch):
    def __init__(self, id: int):
        super().__init__(id)

    def get_ram_type(self) -> RamType:
        return RamType.BLOCK_RAM

    def get_supported_ram_mode(self) -> RamMode:
        pass
