import unittest
from .logical_ram import LogicalRam, RamMode, parse_grouped_LogicalRam


class LogicalRamTestCase(unittest.TestCase):
    def test_RamMode_in(self):
        mode0 = RamMode.SimpleDualPort | RamMode.ROM
        self.assertNotIn(mode0, RamMode)
        self.assertIn(RamMode.SimpleDualPort, mode0)
        self.assertNotIn(RamMode.TrueDualPort, mode0)
        mode1 = RamMode.TrueDualPort
        self.assertIn(mode1, RamMode)
        self.assertIn(RamMode.TrueDualPort, mode1)
        self.assertNotIn(RamMode.ROM, mode1)

    def test_LogicalRam_from_str(self):
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

    def test_parse_grouped_LogicalRam_ordered_indices(self):
        input_str = '''
        Num_Circuits 3
        Circuit	RamID	Mode		Depth	Width
        6	0	SimpleDualPort	45	12
        5	33	ROM           	256	8
        2	30	TrueDualPort  	512	39
        2	20	SinglePort    	2048	32
        '''
        lr_group = parse_grouped_LogicalRam(iter(input_str.splitlines()))
        self.assertEqual(list(lr_group.keys()), sorted(lr_group.keys()))
        for lr_subgroup in lr_group.values():
            self.assertEqual(list(lr_subgroup.keys()),
                             sorted(lr_subgroup.keys()))
