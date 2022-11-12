import unittest
from . import logical_ram


class LogicalRamTestCase(unittest.TestCase):
    def test_from_str(self):
        self.assertEqual(
            logical_ram.LogicalRam.from_str('0	0	SimpleDualPort	45	12'),
            logical_ram.LogicalRam(circuit_id=0, ram_id=0, mode=logical_ram.RamMode.SimpleDualPort, depth=45, width=12))
