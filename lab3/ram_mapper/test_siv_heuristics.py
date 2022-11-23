from collections import Counter
import unittest

from .siv_arch import generate_default_ram_arch
from .siv_heuristics import calculate_fpga_area


class SIVHeuristicsTestCase(unittest.TestCase):
    def test_calculate_fpga_area(self):
        ram_arch = generate_default_ram_arch()
        fpga_area = calculate_fpga_area(ram_arch=ram_arch, logic_block_count=20,
                                        extra_lut_count=33, physical_ram_count=Counter({1: 8, 2: 2}), verbose=False)
        self.assertEqual(fpga_area, 1489518)