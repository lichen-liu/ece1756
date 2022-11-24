import unittest
from .logical_ram import RamMode
from .physical_arch import RamType, RamShape
from .siv_arch import *


class SIVArchTestCase(unittest.TestCase):
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
        self.assertEqual(create_ram_arch_from_str(0, '-b 8192 32 10 1'),
                         BlockRamArch(0, RamShape.from_size(8192, 32), (10, 1)))
        self.assertEqual(create_ram_arch_from_str(0, '-b 131072 128 300 1'),
                         BlockRamArch(0, RamShape.from_size(131072, 128), (300, 1)))
        self.assertEqual(create_ram_arch_from_str(
            0, '-l 1 1'), LUTRamArch(0, (1, 1)))

    def test_create_all_from_strs(self):
        actual = {1: LUTRamArch(1, (1, 1)),
                  2: BlockRamArch(2, RamShape.from_size(8192, 32), (10, 1)),
                  3: BlockRamArch(3, RamShape.from_size(131072, 128), (300, 1))}
        self.assertDictEqual(create_all_ram_arch_from_strs(
            ['-l 1 1', '-b 8192 32 10 1', '-b 131072 128 300 1']), actual)

    def test_create_all_from_str(self):
        actual = {1: LUTRamArch(1, (1, 1)),
                  2: BlockRamArch(2, RamShape.from_size(8192, 32), (10, 1)),
                  3: BlockRamArch(3, RamShape.from_size(131072, 128), (300, 1))}
        self.assertDictEqual(create_all_ram_arch_from_str('-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1'),
                             actual)

    def test_determine_write_decoder_luts(self):
        expected_pair = [(2, 1), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (
            9, 9), (10, 10), (11, 11), (12, 12), (13, 13), (14, 14), (15, 15), (16, 16)]
        for r, expected_result in expected_pair:
            self.assertEqual(determine_write_decoder_luts(r), expected_result)

    def test_determine_read_mux_luts_per_bit(self):
        expected_pair = [(2, 1), (3, 1), (4, 1), (5, 2), (6, 2), (7, 2), (
            8, 3), (9, 3), (10, 3), (11, 4), (12, 4), (13, 4), (14, 5), (15, 5), (16, 5)]
        for r, expected_result in expected_pair:
            self.assertEqual(
                determine_read_mux_luts_per_bit(r), expected_result)

    def test_determine_read_mux_luts(self):
        self.assertEqual(determine_read_mux_luts(r=8, logical_w=30), 3*30)

    def test_determine_extra_luts(self):
        self.assertEqual(determine_extra_luts(
            num_series=8, logical_w=30, ram_mode=RamMode.ROM), 3*30)
        self.assertEqual(determine_extra_luts(
            num_series=8, logical_w=30, ram_mode=RamMode.SinglePort), 3*30 + 8)
        self.assertEqual(determine_extra_luts(
            num_series=8, logical_w=30, ram_mode=RamMode.SimpleDualPort), 3*30 + 8)
        self.assertEqual(determine_extra_luts(
            num_series=8, logical_w=30, ram_mode=RamMode.TrueDualPort), 2*(3*30 + 8))

    def test_generate_default_arch(self):
        self.assertDictEqual(generate_default_ram_arch(), {1: generate_default_lutram(
        ), 2: generate_default_8k_bram(), 3: generate_default_128k_bram()})

    def test_default_lutram_area(self):
        self.assertEqual(generate_default_lutram().get_area(), 40000)

    def test_default_8k_bram_area(self):
        self.assertEqual(generate_default_8k_bram().get_area(), 96506)

    def test_default_128k_bram_area(self):
        self.assertEqual(generate_default_128k_bram().get_area(), 850543)

    def test_logic_block_area(self):
        self.assertEqual(RegularLogicBlockArch().get_area(), 35000)
