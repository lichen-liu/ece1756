import unittest

from .logical_ram import LogicalRam, RamMode, parse_grouped_LogicalRam
from .logical_circuit import LogicalCircuit, merge_grouped_LogicalCircuit, parse_LogicBlock


class LogicalCircuitTestCase(unittest.TestCase):
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

    @staticmethod
    def generate_simple_LogicalCircuit() -> LogicalCircuit:
        logical_rams_str = '''
        Num_Circuits 3
        Circuit	RamID	Mode		Depth	Width
        0	0	SimpleDualPort	45	12
        0	1	ROM	45	12
        0	2	SinglePort	72	21
        1	0	SimpleDualPort	32	18
        2	0	SimpleDualPort	64	36
        '''
        logic_blocks_str = '''
        Circuit	"# Logic blocks (N=10, k=6, fracturable)"
        0	2941
        1	2906
        2	1836
        '''
        actual_lcs = merge_grouped_LogicalCircuit(logic_blocks=parse_LogicBlock(iter(
            logic_blocks_str.splitlines())), logical_rams=parse_grouped_LogicalRam(iter(logical_rams_str.splitlines())))
        return actual_lcs

    def test_merge_grouped_LogicalCircuit(self):
        lc0 = LogicalCircuit(circuit_id=0, num_logic_blocks=2941, rams={
            0: LogicalRam(circuit_id=0, ram_id=0, mode=RamMode.SimpleDualPort, depth=45, width=12),
            1: LogicalRam(circuit_id=0, ram_id=1, mode=RamMode.ROM, depth=45, width=12),
            2: LogicalRam(circuit_id=0, ram_id=2, mode=RamMode.SinglePort, depth=72, width=21)})
        lc1 = LogicalCircuit(circuit_id=1, num_logic_blocks=2906, rams={
            0: LogicalRam(circuit_id=1, ram_id=0, mode=RamMode.SimpleDualPort, depth=32, width=18)})
        lc2 = LogicalCircuit(circuit_id=2, num_logic_blocks=1836, rams={
            0: LogicalRam(circuit_id=2, ram_id=0, mode=RamMode.SimpleDualPort, depth=64, width=36)})
        expected_lcs = {0: lc0, 1: lc1, 2: lc2}
        actual_lcs = self.generate_simple_LogicalCircuit()
        self.assertDictEqual(actual_lcs, expected_lcs)

    def test_get_ram_modes(self):
        lc = self.generate_simple_LogicalCircuit()[0]
        self.assertDictEqual(lc.get_ram_modes(), {
                             0: RamMode.SimpleDualPort, 1: RamMode.ROM, 2: RamMode.SinglePort})
