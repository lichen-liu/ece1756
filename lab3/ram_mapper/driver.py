from ram_mapper.physical_ram import RamShape
from ram_mapper.stratix_iv_ram import ConcreteBlockRamArch
from ram_mapper import logical_ram


def run():
    logical_ram.read_grouped_LogicalRam_from_file('logical_rams.txt')

    bram = ConcreteBlockRamArch(0, RamShape.from_size_width(1024, 32), 10)
    print(bram)
    # x = logical_ram.RamMode.SimpleDualPort | logical_ram.RamMode.TrueDualPort
    # print(x)
    # print(type(x))
