import unittest
from ram_mapper.mapping_config import CircuitRamConfig, LogicalRamConfig, PhysicalRamConfig, RamMode, CombinedLogicalRamConfig, RamSplitDimension


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
        crc = self.generate_simple_CircuitRamConfig()
        self.assertTrue(crc.verify())

    def test_CircuitRamConfig_simple_print(self):
        crc = self.generate_simple_CircuitRamConfig()
        crc_expected_str = '1 2 0 LW 12 LD 45 ID 0 S 1 P 2 Type 1 Mode SimpleDualPort W 10 D 64'
        self.assertEqual(crc.print(0), crc_expected_str)

    def test_CircuitRamConfig_simple_update_extra_luts(self):
        crc = self.generate_simple_CircuitRamConfig()
        self.assertEqual(crc.update_extra_luts(RamMode.SimpleDualPort), 0)

    def test_CircuitRamConfig_verify_invalid(self):
        def generate_crc0():
            lrc = LogicalRamConfig(logical_width=12, logical_depth=45)
            crc = CircuitRamConfig(circuit_id=1, ram_id=2,
                                   num_extra_lut=0, lrc=lrc)
            return crc
        crc0 = generate_crc0()
        self.assertFalse(crc0.verify())

    def generate_2level_CircuitRamConfig(self):
        prc0 = PhysicalRamConfig(id=0, num_series=1, num_parallel=4, ram_arch_id=2,
                                 ram_mode=RamMode.SinglePort, width=8, depth=1024)
        lrc0 = LogicalRamConfig(logical_width=30, logical_depth=1024, prc=prc0)
        prc1 = PhysicalRamConfig(id=1, num_series=1, num_parallel=2, ram_arch_id=1,
                                 ram_mode=RamMode.SinglePort, width=20, depth=32)
        lrc1 = LogicalRamConfig(logical_width=30, logical_depth=1, prc=prc1)

        clrc = CombinedLogicalRamConfig(
            split=RamSplitDimension.series, lrc_l=lrc0, lrc_r=lrc1)
        lrc = LogicalRamConfig(logical_width=30, logical_depth=1025, clrc=clrc)

        crc = CircuitRamConfig(circuit_id=3, ram_id=7,
                               num_extra_lut=31, lrc=lrc)
        return crc

    def test_CircuitRamConfig_2level_verify(self):
        crc = self.generate_2level_CircuitRamConfig()
        self.assertTrue(crc.verify())

    def test_CircuitRamConfig_2level_print(self):
        crc = self.generate_2level_CircuitRamConfig()
        crc_expected_str = '''3 7 31 LW 30 LD 1025 series
    LW 30 LD 1024 ID 0 S 1 P 4 Type 2 Mode SinglePort W 8 D 1024
    LW 30 LD 1 ID 1 S 1 P 2 Type 1 Mode SinglePort W 20 D 32'''
        self.assertEqual(crc.print(0), crc_expected_str)

    def test_CircuitRamConfig_2level_update_extra_luts(self):
        crc = self.generate_2level_CircuitRamConfig()
        self.assertEqual(crc.update_extra_luts(RamMode.SinglePort), 31)

    def generate_3level_CircuitRamConfig(self):
        prc0 = PhysicalRamConfig(id=0, num_series=1, num_parallel=4, ram_arch_id=1,
                                 ram_mode=RamMode.SinglePort, width=20, depth=32)
        lrc0 = LogicalRamConfig(logical_width=30, logical_depth=8, prc=prc0)

        prc1 = PhysicalRamConfig(id=1, num_series=1, num_parallel=1, ram_arch_id=3,
                                 ram_mode=RamMode.SinglePort, width=16, depth=8192)
        lrc1 = LogicalRamConfig(logical_width=16, logical_depth=8192, prc=prc1)
        prc2 = PhysicalRamConfig(id=2, num_series=1, num_parallel=14, ram_arch_id=2,
                                 ram_mode=RamMode.SinglePort, width=1, depth=8192)
        lrc2 = LogicalRamConfig(logical_width=14, logical_depth=8192, prc=prc2)
        clrc12 = CombinedLogicalRamConfig(
            split=RamSplitDimension.parallel, lrc_l=lrc1, lrc_r=lrc2)
        lrc12 = LogicalRamConfig(
            logical_width=30, logical_depth=8192, clrc=clrc12)

        clrc012 = CombinedLogicalRamConfig(
            split=RamSplitDimension.series, lrc_l=lrc0, lrc_r=lrc12)
        lrc012 = LogicalRamConfig(
            logical_width=30, logical_depth=8200, clrc=clrc012)

        crc = CircuitRamConfig(circuit_id=3, ram_id=8,
                               num_extra_lut=31, lrc=lrc012)
        return crc

    def test_CircuitRamConfig_3level_verify(self):
        crc = self.generate_3level_CircuitRamConfig()
        self.assertTrue(crc.verify())

    def test_CircuitRamConfig_3level_print(self):
        crc = self.generate_3level_CircuitRamConfig()
        crc_expected_str = '''3 8 31 LW 30 LD 8200 series
    LW 30 LD 8 ID 0 S 1 P 4 Type 1 Mode SinglePort W 20 D 32
    LW 30 LD 8192 parallel
        LW 16 LD 8192 ID 1 S 1 P 1 Type 3 Mode SinglePort W 16 D 8192
        LW 14 LD 8192 ID 2 S 1 P 14 Type 2 Mode SinglePort W 1 D 8192'''
        self.assertEqual(crc.print(0), crc_expected_str)

    def test_CircuitRamConfig_3level_update_extra_luts(self):
        crc = self.generate_3level_CircuitRamConfig()
        self.assertEqual(crc.update_extra_luts(RamMode.SinglePort), 31)
        self.skipTest('Not implemented')
