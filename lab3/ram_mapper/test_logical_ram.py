import unittest
from .logical_ram import LogicalRam, RamMode


class LogicalRamTestCase(unittest.TestCase):
    def test_from_str(self):
        self.assertEqual(
            LogicalRam.from_str('0	0	SimpleDualPort	45	12'),
            LogicalRam(circuit_id=0, ram_id=0, mode=RamMode.SimpleDualPort, depth=45, width=12))
        self.assertEqual(
            LogicalRam.from_str('0	33	ROM           	256	8'),
            LogicalRam(circuit_id=0, ram_id=33, mode=RamMode.ROM, depth=256, width=8))
        self.assertEqual(
            LogicalRam.from_str('5	99	TrueDualPort  	512	39'),
            LogicalRam(circuit_id=5, ram_id=99, mode=RamMode.TrueDualPort, depth=512, width=39))
        self.assertEqual(
            LogicalRam.from_str('6	20	SinglePort    	2048	32'),
            LogicalRam(circuit_id=6, ram_id=20, mode=RamMode.SinglePort, depth=2048, width=32))