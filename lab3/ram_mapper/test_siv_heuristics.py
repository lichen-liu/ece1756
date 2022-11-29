import unittest

from .siv_arch import DEFAULT_RAM_ARCH_STR, SIVArch
from .siv_heuristics import calculate_fpga_qor


class SIVHeuristicsTestCase(unittest.TestCase):
    def test_calculate_fpga_area(self):
        archs = SIVArch.from_str(DEFAULT_RAM_ARCH_STR)
        fpga_qor = calculate_fpga_qor(archs=archs, logic_block_count=20,
                                      extra_lut_count=33, physical_ram_count=[0, 8, 2], verbose=False)
        self.assertEqual(fpga_qor.fpga_area, 1489518)
