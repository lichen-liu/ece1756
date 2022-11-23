import unittest

from .stratix_iv_arch import generate_default_arch
from .stratix_iv_heuristics import calculate_fpga_area


class StratixIVHeuristicsTestCase(unittest.TestCase):
    def test_calculate_fpga_area(self):
        ram_arch = generate_default_arch()
