import unittest
from ram_mapper.mapping_config import CircuitRamConfig, LogicalRamConfig, PhysicalRamConfig, RamMode


class MappingConfigTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # from ram_mapper.utils import init_logger
        # init_logger()
        return super().setUp()

    def generate_simple_CircuitRamConfig(self):
        prc = PhysicalRamConfig(id=0, num_series=1, num_parallel=2, ram_arch_id=1,
                                ram_mode=RamMode.SimpleDualPort, width=10, depth=64)
        lrc = LogicalRamConfig(logical_width=12, logical_depth=45, prc=prc)
        crc = CircuitRamConfig(circuit_id=1, ram_id=2,
                               num_extra_lut=0, lrc=lrc)
        return crc

    def test_CircuitRamConfig_simple_verify(self):
        crc0 = self.generate_simple_CircuitRamConfig()
        self.assertTrue(crc0.verify())

    def test_CircuitRamConfig_simple_print(self):
        crc0 = self.generate_simple_CircuitRamConfig()
        crc0_expected_str = '1 2 0 LW 12 LD 45 ID 0 S 1 P 2 Type 1 Mode SimpleDualPort W 10 D 64'
        self.assertEqual(crc0.print(0), crc0_expected_str)

    def test_CircuitRamConfig_verify_invalid(self):
        def generate_crc0():
            lrc = LogicalRamConfig(logical_width=12, logical_depth=45)
            crc = CircuitRamConfig(circuit_id=1, ram_id=2,
                                   num_extra_lut=0, lrc=lrc)
            return crc
        crc0 = generate_crc0()
        self.assertFalse(crc0.verify())
