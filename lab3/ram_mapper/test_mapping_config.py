import unittest

from .logical_ram import RamShape, RamShapeFit
from .mapping_config import CircuitConfig, RamConfig, LogicalRamConfig, PhysicalRamConfig, RamMode, CombinedLogicalRamConfig, RamSplitDimension


class MappingConfigTestCase(unittest.TestCase):
    @staticmethod
    def generate_1level_RamConfig() -> RamConfig:
        prc = PhysicalRamConfig(id=0, physical_shape_fit=RamShapeFit(num_series=1, num_parallel=2), ram_arch_id=1,
                                ram_mode=RamMode.SimpleDualPort, physical_shape=RamShape(width=10, depth=64))
        lrc = LogicalRamConfig(
            logical_shape=RamShape(width=12, depth=45), prc=prc)
        rc = RamConfig(circuit_id=1, ram_id=2, lrc=lrc,
                       ram_mode=RamMode.SimpleDualPort)
        return rc

    def test_RamConfig_1level_serialize(self):
        rc = self.generate_1level_RamConfig()
        rc_expected_str = '1 2 0 LW 12 LD 45 ID 0 S 1 P 2 Type 1 Mode SimpleDualPort W 10 D 64'
        self.assertEqual(rc.serialize(0), rc_expected_str)

    def test_RamConfig_1level_get_extra_lut_count(self):
        rc = self.generate_1level_RamConfig()
        self.assertEqual(rc.get_extra_lut_count(), 0)

    def test_RamConfig_1level_get_physical_ram_count(self):
        rc = self.generate_1level_RamConfig()
        self.assertListEqual(rc.get_physical_ram_count(), [0, 2])

    def test_RamConfig_1level_ram_mode(self):
        rc = self.generate_1level_RamConfig()
        self.assertEqual(rc.ram_mode, RamMode.SimpleDualPort)

    def test_RamConfig_1level_execute_on_leaf(self):
        rc = self.generate_1level_RamConfig()
        counter = 0

        def callback(lrc: LogicalRamConfig):
            nonlocal counter
            counter += 1
        rc.execute_on_leaf(callback)
        self.assertEqual(counter, 1)

    @staticmethod
    def generate_2level_RamConfig() -> RamConfig:
        prc0 = PhysicalRamConfig(id=0, physical_shape_fit=RamShapeFit(num_series=1, num_parallel=4), ram_arch_id=2,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=8, depth=1024))
        lrc0 = LogicalRamConfig(logical_shape=RamShape(
            width=30, depth=1024), prc=prc0)
        prc1 = PhysicalRamConfig(id=1, physical_shape_fit=RamShapeFit(num_series=1, num_parallel=2), ram_arch_id=1,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=20, depth=32))
        lrc1 = LogicalRamConfig(
            logical_shape=RamShape(width=30, depth=1), prc=prc1)

        clrc = CombinedLogicalRamConfig(
            split=RamSplitDimension.series, lrc_l=lrc0, lrc_r=lrc1)
        lrc = LogicalRamConfig(logical_shape=RamShape(
            width=30, depth=1025), clrc=clrc)

        rc = RamConfig(circuit_id=3, ram_id=7, lrc=lrc,
                       ram_mode=RamMode.SinglePort)
        return rc

    def test_RamConfig_2level_serialize(self):
        rc = self.generate_2level_RamConfig()
        rc_expected_str = '''3 7 31 LW 30 LD 1025 series
    LW 30 LD 1024 ID 0 S 1 P 4 Type 2 Mode SinglePort W 8 D 1024
    LW 30 LD 1 ID 1 S 1 P 2 Type 1 Mode SinglePort W 20 D 32'''
        self.assertEqual(rc.serialize(0), rc_expected_str)

    def test_RamConfig_2level_get_extra_lut_count(self):
        rc = self.generate_2level_RamConfig()
        self.assertEqual(rc.get_extra_lut_count(), 31)

    def test_RamConfig_2level_get_physical_ram_count(self):
        rc = self.generate_2level_RamConfig()
        self.assertListEqual(rc.get_physical_ram_count(), [0, 2, 4])

    def test_RamConfig_2level_ram_mode(self):
        rc = self.generate_2level_RamConfig()
        self.assertEqual(rc.ram_mode, RamMode.SinglePort)

    def test_RamConfig_2level_execute_on_leaf(self):
        rc = self.generate_2level_RamConfig()
        counter = 0

        def callback(lrc: LogicalRamConfig):
            nonlocal counter
            counter += 1
        rc.execute_on_leaf(callback)
        self.assertEqual(counter, 2)

    @ staticmethod
    def generate_3level_RamConfig() -> RamConfig:
        prc0 = PhysicalRamConfig(id=0, physical_shape_fit=RamShapeFit(num_series=1, num_parallel=4), ram_arch_id=1,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=20, depth=32))
        lrc0 = LogicalRamConfig(
            logical_shape=RamShape(width=30, depth=8), prc=prc0)

        prc1 = PhysicalRamConfig(id=1, physical_shape_fit=RamShapeFit(num_series=1, num_parallel=1), ram_arch_id=3,
                                 ram_mode=RamMode.SinglePort, physical_shape=RamShape(width=16, depth=8192))
        lrc1 = LogicalRamConfig(logical_shape=RamShape(
            width=16, depth=8192), prc=prc1)
        prc2 = PhysicalRamConfig(id=2, physical_shape_fit=RamShapeFit(num_series=1, num_parallel=14), ram_arch_id=2,
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

        rc = RamConfig(circuit_id=3, ram_id=8, lrc=lrc012,
                       ram_mode=RamMode.SinglePort)
        return rc

    def test_RamConfig_3level_serialize(self):
        rc = self.generate_3level_RamConfig()
        rc_expected_str = '''3 8 31 LW 30 LD 8200 series
    LW 30 LD 8 ID 0 S 1 P 4 Type 1 Mode SinglePort W 20 D 32
    LW 30 LD 8192 parallel
        LW 16 LD 8192 ID 1 S 1 P 1 Type 3 Mode SinglePort W 16 D 8192
        LW 14 LD 8192 ID 2 S 1 P 14 Type 2 Mode SinglePort W 1 D 8192'''
        self.assertEqual(rc.serialize(0), rc_expected_str)

    def test_RamConfig_3level_get_extra_lut_count(self):
        rc = self.generate_3level_RamConfig()
        self.assertEqual(rc.get_extra_lut_count(), 31)

    def test_RamConfig_3level_get_physical_ram_count(self):
        rc = self.generate_3level_RamConfig()
        self.assertListEqual(rc.get_physical_ram_count(), [0, 4, 14, 1])

    def test_RamConfig_3level_ram_mode(self):
        rc = self.generate_3level_RamConfig()
        self.assertEqual(rc.ram_mode, RamMode.SinglePort)

    def test_RamConfig_3level_execute_on_leaf(self):
        rc = self.generate_3level_RamConfig()
        counter = 0

        def callback(lrc: LogicalRamConfig):
            nonlocal counter
            counter += 1
        rc.execute_on_leaf(callback)
        self.assertEqual(counter, 3)

    def test_RamConfig_share_write_decoder_lut_count(self):
        rc_expected_str = '''0 416 22 LW 21 LD 72 parallel
    LW 20 LD 72 ID 416 S 2 P 2 Type 1 Mode SimpleDualPort W 10 D 64
    LW 1 LD 72 ID 721 S 2 P 1 Type 1 Mode SimpleDualPort W 10 D 64'''
        lrc_l = LogicalRamConfig(
            logical_shape=RamShape(width=20, depth=72),
            prc=PhysicalRamConfig(
                id=416,
                physical_shape_fit=RamShapeFit(num_series=2, num_parallel=2),
                ram_arch_id=1,
                ram_mode=RamMode.SimpleDualPort,
                physical_shape=RamShape(width=10, depth=64)))
        lrc_r = LogicalRamConfig(
            logical_shape=RamShape(width=1, depth=72),
            prc=PhysicalRamConfig(
                id=721,
                physical_shape_fit=RamShapeFit(num_series=2, num_parallel=1),
                ram_arch_id=1,
                ram_mode=RamMode.SimpleDualPort,
                physical_shape=RamShape(width=10, depth=64)))
        rc = RamConfig(
            circuit_id=0,
            ram_id=416,
            lrc=LogicalRamConfig(
                logical_shape=RamShape(width=21, depth=72),
                clrc=CombinedLogicalRamConfig(
                    split=RamSplitDimension.parallel,
                    lrc_l=lrc_l,
                    lrc_r=lrc_r)),
            ram_mode=RamMode.SimpleDualPort)
        self.assertEqual(rc.serialize(0), rc_expected_str)
        self.assertEqual(rc.get_extra_lut_count(), 22)

    @staticmethod
    def generate_2_3_level_CircuitConfig() -> CircuitConfig:
        cc = CircuitConfig(circuit_id=3)
        cc.insert_ram_config(MappingConfigTestCase.generate_2level_RamConfig())
        cc.insert_ram_config(MappingConfigTestCase.generate_3level_RamConfig())
        return cc

    def test_CircuitConfig_2_3_level_get_physical_ram_count(self):
        cc = self.generate_2_3_level_CircuitConfig()
        self.assertListEqual(cc.get_physical_ram_count(), [0, 6, 18, 1])

    def test_CircuitConfig_2_3_level_get_extra_lut_count(self):
        cc = self.generate_2_3_level_CircuitConfig()
        self.assertEqual(cc.get_extra_lut_count(), 62)
