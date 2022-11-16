import unittest
from ram_mapper.physical_ram import RamShape


class PhysicalRamTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # from ram_mapper.utils import init_logger
        # init_logger()
        return super().setUp()

    def test_RamShape_from_size(self):
        self.assertEqual(RamShape.from_size(512, 32), RamShape(32, 16))
        self.assertEqual(RamShape.from_size(8192, 32), RamShape(32, 256))
        self.assertEqual(RamShape.from_size(8192, 16), RamShape(16, 512))
        self.assertEqual(RamShape.from_size(131072, 128), RamShape(128, 1024))
        self.assertEqual(RamShape.from_size(131072, 64), RamShape(64, 2048))
        with self.assertRaises(AssertionError):
            RamShape.from_size(16, 9)

    def test_RamShape_get_size(self):
        self.assertEqual(RamShape.from_size(8192, 32).get_size(), 8192)
        self.assertEqual(RamShape.from_size(131072, 32).get_size(), 131072)
