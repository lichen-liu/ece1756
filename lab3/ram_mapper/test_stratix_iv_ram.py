import unittest
from ram_mapper.logical_ram import RamMode
from ram_mapper.physical_ram import RamType, RamShape
from ram_mapper.stratix_iv_ram import BlockRamArch, create_from_str, LUTRamArch, create_all_from_strs, create_all_from_str


class StratixIVRamTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # from ram_mapper.utils import init_logger
        # init_logger()
        return super().setUp()

    def test_BlockRamArch(self):
        ram = BlockRamArch(0, RamShape.from_size(256, 16), (10, 1))
        self.assertEqual(ram.get_id(), 0)
        self.assertEqual(ram.get_max_width(), RamShape(16, 16))
        self.assertEqual(ram.get_ram_type(), RamType.BLOCK_RAM)
        self.assertEqual(ram.get_ratio_of_LB(), (10, 1))
        self.assertEqual(ram.get_size(), 256)
        self.assertEqual(ram.get_supported_mode(), RamMode.ROM |
                         RamMode.SimpleDualPort | RamMode.SinglePort | RamMode.TrueDualPort)

        full_width_shapes = [RamShape.from_size(256, 16),
                             RamShape.from_size(256, 8),
                             RamShape.from_size(256, 4),
                             RamShape.from_size(256, 2),
                             RamShape.from_size(256, 1)]
        self.assertEqual(ram.get_shapes_for_mode(
            RamMode.SimpleDualPort), full_width_shapes)
        self.assertEqual(ram.get_shapes_for_mode(
            RamMode.ROM), full_width_shapes)
        self.assertEqual(ram.get_shapes_for_mode(
            RamMode.SinglePort), full_width_shapes)

        reduced_width_shapes = [RamShape.from_size(256, 8),
                                RamShape.from_size(256, 4),
                                RamShape.from_size(256, 2),
                                RamShape.from_size(256, 1)]
        self.assertEqual(ram.get_shapes_for_mode(
            RamMode.TrueDualPort), reduced_width_shapes)

    def test_create_from_str(self):
        self.assertEqual(create_from_str(0, '-b 8192 32 10 1'),
                         BlockRamArch(0, RamShape.from_size(8192, 32), (10, 1)))
        self.assertEqual(create_from_str(0, '-b 131072 128 300 1'),
                         BlockRamArch(0, RamShape.from_size(131072, 128), (300, 1)))
        self.assertEqual(create_from_str(0, '-l 1 1'), LUTRamArch(0, (1, 1)))

    def test_create_all_from_strs(self):
        actual = [LUTRamArch(0, (1, 1)),
                  BlockRamArch(1, RamShape.from_size(8192, 32), (10, 1)),
                  BlockRamArch(2, RamShape.from_size(131072, 128), (300, 1))]
        self.assertEqual(create_all_from_strs(
            ['-l 1 1', '-b 8192 32 10 1', '-b 131072 128 300 1']), actual)

    def test_create_all_from_str(self):
        actual = [LUTRamArch(0, (1, 1)),
                  BlockRamArch(1, RamShape.from_size(8192, 32), (10, 1)),
                  BlockRamArch(2, RamShape.from_size(131072, 128), (300, 1))]
        self.assertEqual(create_all_from_str('-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1'),
                         actual)
