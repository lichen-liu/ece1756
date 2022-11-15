from ram_mapper import logical_ram


def run():
    logical_ram.read_grouped_LogicalRam_from_file('logical_rams.txt')

    # x = logical_ram.RamMode.SimpleDualPort | logical_ram.RamMode.TrueDualPort
    # print(x)
    # print(type(x))
