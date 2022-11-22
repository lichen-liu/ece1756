import unittest

from .logical_ram import LogicalRam, RamMode, parse_grouped_LogicalRam
from .logical_circuit import LogicalCircuit, merge_grouped_LogicalCircuit, parse_LogicBlock


class LogicalCircuitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # from .utils import init_logger
        # init_logger()
        return super().setUp()

    def test_parse_LogicBlock(self):
        input_str = '''
        Circuit	"# Logic blocks (N=10, k=6, fracturable)"
        0	2941
        1	2906
        2	1836
        3	2808
        4	7907
        '''
        lbs = parse_LogicBlock(iter(input_str.splitlines()))
        self.assertListEqual(list(lbs.items()), [
                             (0, 2941), (1, 2906), (2, 1836), (3, 2808), (4, 7907)])

    def test_merge_grouped_LogicalCircuit(self):
        logical_rams_str = '''
        Num_Circuits 3
        Circuit	RamID	Mode		Depth	Width
        0	0	SimpleDualPort	45	12
        1	0	SimpleDualPort	32	18
        2	0	SimpleDualPort	64	36
        '''
        logic_blocks_str = '''
        Circuit	"# Logic blocks (N=10, k=6, fracturable)"
        0	2941
        1	2906
        2	1836
        '''
        lc0 = LogicalCircuit(circuit_id=0, num_logic_blocks=2941, rams={0: LogicalRam(
            circuit_id=0, ram_id=0, mode=RamMode.SimpleDualPort, depth=45, width=12)})
        lc1 = LogicalCircuit(circuit_id=1, num_logic_blocks=2906, rams={0: LogicalRam(
            circuit_id=1, ram_id=0, mode=RamMode.SimpleDualPort, depth=32, width=18)})
        lc2 = LogicalCircuit(circuit_id=2, num_logic_blocks=1836, rams={0: LogicalRam(
            circuit_id=2, ram_id=0, mode=RamMode.SimpleDualPort, depth=64, width=36)})
        expected_lcs = {0: lc0, 1: lc1, 2: lc2}
        actual_lcs = merge_grouped_LogicalCircuit(logic_blocks=parse_LogicBlock(iter(
            logic_blocks_str.splitlines())), logical_rams=parse_grouped_LogicalRam(iter(logical_rams_str.splitlines())))
        self.assertDictEqual(actual_lcs, expected_lcs)
