import unittest
from .logical_circuit import parse_LogicBlock


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
