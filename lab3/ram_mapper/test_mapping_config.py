from collections import Counter
import unittest

from .logical_ram import RamShape
from .mapping_config import CircuitConfig, RamConfig, LogicalRamConfig, PhysicalRamConfig, RamMode, CombinedLogicalRamConfig, RamSplitDimension


class MappingConfigTestCase(unittest.TestCase):
    @staticmethod
    def generate_1level_RamConfig() -> RamConfig:
        prc = PhysicalRamConfig(id=0, num_series=1, num_parallel=2, ram_arch_id=1,
                                ram_mode=RamMode.SimpleDualPort, physical_shape=RamShape(width=10, depth=64))
        lrc = LogicalRamConfig(
            logical_shape=RamShape(width=12, depth=45), prc=prc)
        rc = RamConfig(circuit_id=1, ram_id=2,
                       num_extra_lut=0, lrc=lrc)
        return rc

    def test_RamConfig_1level_verify(self):
        rc = self.generate_1level_RamConfig()
        self.assertTrue(rc.verify())

    def test_RamConfig_1level_serialize(self):
        rc = self.generate_1level_RamConfig()
        rc_expected_str = '1 2 0 LW 12 LD 45 ID 0 S 1 P 2 Type 1 Mode SimpleDualPort W 10 D 64'
        self.assertEqual(rc.serialize(0), rc_expected_str)

    def test_RamConfig_1level_update_extra_luts(self):
        rc = self.generate_1level_RamConfig()
        self.assertEqual(rc.update_extra_luts(RamMode.SimpleDualPort), 0)

    def test_RamConfig_1level_get_physical_ram_count(self):
        rc = self.generate_1level_RamConfig()
        self.assertDictEqual(rc.get_physical_ram_count(), Counter({1: 2}))

    def test_RamConfig_verify_invalid(self):
        def generate_rc0():
            lrc = LogicalRamConfig(logical_shape=RamShape(width=12, depth=45))
            rc = RamConfig(circuit_id=1, ram_id=2,
                           num_extra_lut=0, lrc=lrc)
            return rc
        rc0 = generate_rc0()
        self.assertFalse(rc0.verify())

    @staticmethod
    def generate_2level_RamConfig() -> RamConfig:
        prc0 = PhysicalRamConfig(id=0, num_series=1, num_parallel=4, ram_arch_id=2,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=8, depth=1024))
        lrc0 = LogicalRamConfig(logical_shape=RamShape(
            width=30, depth=1024), prc=prc0)
        prc1 = PhysicalRamConfig(id=1, num_series=1, num_parallel=2, ram_arch_id=1,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=20, depth=32))
        lrc1 = LogicalRamConfig(
            logical_shape=RamShape(width=30, depth=1), prc=prc1)

        clrc = CombinedLogicalRamConfig(
            split=RamSplitDimension.series, lrc_l=lrc0, lrc_r=lrc1)
        lrc = LogicalRamConfig(logical_shape=RamShape(
            width=30, depth=1025), clrc=clrc)

        rc = RamConfig(circuit_id=3, ram_id=7,
                       num_extra_lut=31, lrc=lrc)
        return rc

    def test_RamConfig_2level_verify(self):
        rc = self.generate_2level_RamConfig()
        self.assertTrue(rc.verify())

    def test_RamConfig_2level_serialize(self):
        rc = self.generate_2level_RamConfig()
        rc_expected_str = '''3 7 31 LW 30 LD 1025 series
    LW 30 LD 1024 ID 0 S 1 P 4 Type 2 Mode SinglePort W 8 D 1024
    LW 30 LD 1 ID 1 S 1 P 2 Type 1 Mode SinglePort W 20 D 32'''
        self.assertEqual(rc.serialize(0), rc_expected_str)

    def test_RamConfig_2level_update_extra_luts(self):
        rc = self.generate_2level_RamConfig()
        self.assertEqual(rc.update_extra_luts(RamMode.SinglePort), 31)

    def test_RamConfig_2level_get_physical_ram_count(self):
        rc = self.generate_2level_RamConfig()
        self.assertDictEqual(rc.get_physical_ram_count(),
                             Counter({1: 2, 2: 4}))

    @staticmethod
    def generate_3level_RamConfig() -> RamConfig:
        prc0 = PhysicalRamConfig(id=0, num_series=1, num_parallel=4, ram_arch_id=1,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=20, depth=32))
        lrc0 = LogicalRamConfig(
            logical_shape=RamShape(width=30, depth=8), prc=prc0)

        prc1 = PhysicalRamConfig(id=1, num_series=1, num_parallel=1, ram_arch_id=3,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=16, depth=8192))
        lrc1 = LogicalRamConfig(logical_shape=RamShape(
            width=16, depth=8192), prc=prc1)
        prc2 = PhysicalRamConfig(id=2, num_series=1, num_parallel=14, ram_arch_id=2,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=1, depth=8192))
        lrc2 = LogicalRamConfig(logical_shape=RamShape(
            width=14, depth=8192), prc=prc2)
        clrc12 = CombinedLogicalRamConfig(
            split=RamSplitDimension.parallel, lrc_l=lrc1, lrc_r=lrc2)
        lrc12 = LogicalRamConfig(
            logical_shape=RamShape(width=30, depth=8192), clrc=clrc12)

        clrc012 = CombinedLogicalRamConfig(
            split=RamSplitDimension.series, lrc_l=lrc0, lrc_r=lrc12)
        lrc012 = LogicalRamConfig(
            logical_shape=RamShape(width=30, depth=8200), clrc=clrc012)

        rc = RamConfig(circuit_id=3, ram_id=8,
                       num_extra_lut=31, lrc=lrc012)
        return rc

    def test_RamConfig_3level_verify(self):
        rc = self.generate_3level_RamConfig()
        self.assertTrue(rc.verify())

    def test_RamConfig_3level_serialize(self):
        rc = self.generate_3level_RamConfig()
        rc_expected_str = '''3 8 31 LW 30 LD 8200 series
    LW 30 LD 8 ID 0 S 1 P 4 Type 1 Mode SinglePort W 20 D 32
    LW 30 LD 8192 parallel
        LW 16 LD 8192 ID 1 S 1 P 1 Type 3 Mode SinglePort W 16 D 8192
        LW 14 LD 8192 ID 2 S 1 P 14 Type 2 Mode SinglePort W 1 D 8192'''
        self.assertEqual(rc.serialize(0), rc_expected_str)

    def test_RamConfig_3level_update_extra_luts(self):
        rc = self.generate_3level_RamConfig()
        self.assertEqual(rc.update_extra_luts(RamMode.SinglePort), 31)

    def test_RamConfig_3level_get_physical_ram_count(self):
        rc = self.generate_3level_RamConfig()
        self.assertDictEqual(rc.get_physical_ram_count(),
                             Counter({1: 4, 2: 14, 3: 1}))

    @staticmethod
    def generate_2_3_level_CircuitConfig() -> CircuitConfig:
        cc = CircuitConfig(circuit_id=3)
        cc.insert_ram_config(MappingConfigTestCase.generate_2level_RamConfig())
        cc.insert_ram_config(MappingConfigTestCase.generate_3level_RamConfig())
        return cc

    def test_CircuitConfig_2_3_level_get_physical_ram_count(self):
        cc = self.generate_2_3_level_CircuitConfig()
        self.assertDictEqual(cc.get_physical_ram_count(),
                             Counter({1: 6, 2: 18, 3: 1}))

    def test_CircuitConfig_2_3_level_get_extra_lut_count(self):
        cc = self.generate_2_3_level_CircuitConfig()
        self.assertEqual(cc.get_extra_lut_count(
            ram_modes={7: RamMode.SinglePort, 8: RamMode.SinglePort}), 62)
