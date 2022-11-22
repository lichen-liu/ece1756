import unittest
from .utils import highest_pow2_below, all_pow2_below, is_pow2, make_sorted_2d_dict


class UtilsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # from .utils import init_logger
        # init_logger()
        return super().setUp()

    def test_highest_pow2_below(self):
        result_pair = [(1, 1), (2, 2), (3, 2), (4, 4),
                       (5, 4), (6, 4), (7, 4), (8, 8),
                       (9, 8), (10, 8), (11, 8), (12, 8),
                       (13, 8), (14, 8), (15, 8), (16, 16),
                       (17, 16), (31, 16), (32, 32), (33, 32),
                       (63, 32), (64, 64), (65, 64), (127, 64),
                       (128, 128), (129, 128), (255, 128), (256, 256),
                       (257, 256), (511, 256), (512, 512), (513, 512),
                       (1023, 512), (1024, 1024), (2047, 1024), (2048, 2048)]
        for x, golden_ans in result_pair:
            self.assertEqual(highest_pow2_below(x), golden_ans)

    def test_all_pow2_below(self):
        self.assertEqual(all_pow2_below(1), [1])
        self.assertEqual(all_pow2_below(2), [2, 1])
        self.assertEqual(all_pow2_below(15), [8, 4, 2, 1])
        self.assertEqual(all_pow2_below(16), [16, 8, 4, 2, 1])
        self.assertEqual(all_pow2_below(17), [16, 8, 4, 2, 1])

    def test_is_pow2(self):
        expected_pair = [(1, True), (2, True), (3, False), (4, True), (5, False), (6, False), (7, False), (8, True),
                         (9, False), (10, False), (11, False), (12, False), (13, False), (14, False), (15, False), (16, True)]

        for n, expected_result in expected_pair:
            self.assertEqual(is_pow2(n), expected_result)

    def test_make_sorted_2d_dict(self):
        raw_dict = {3: {2: 'a', 0: 'b'}, 2: {
            9: 'c', 5: 'd'}, 0: {1: 'e', 6: 'f'}}
        sorted_dict = make_sorted_2d_dict(raw_dict)
        self.assertListEqual(list(sorted_dict.keys()), [0, 2, 3])
        self.assertListEqual(list(sorted_dict[0].keys()), [1, 6])
        self.assertListEqual(list(sorted_dict[2].keys()), [5, 9])
        self.assertListEqual(list(sorted_dict[3].keys()), [0, 2])
