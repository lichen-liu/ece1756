import logging
import math
from typing import List


def init_logger(level=logging.DEBUG):
    # Line number : ":%(lineno)d"
    # TODO: set default to logging.INFO
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)-6s [%(filename)s] %(message)s',
                        datefmt='%Y%m%d:%H:%M:%S', level=level)


def highest_pow2_below(n: int) -> int:
    p = int(math.log(n, 2))
    return int(pow(2, p))


def all_pow2_below(x: int) -> List[int]:
    def all_pow2_below_helper(a: int, l: List[int]) -> List[int]:
        if a >= 1:
            a = highest_pow2_below(a)
            l.append(a)
            if a > 1:
                return all_pow2_below_helper(a - 1, l)
        return l
    return all_pow2_below_helper(x, [])
