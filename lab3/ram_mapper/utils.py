import logging
import math


def init_logger(level=logging.DEBUG):
    # Line number : ":%(lineno)d"
    # TODO: set default to logging.INFO
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)-6s [%(filename)s] %(message)s',
                        datefmt='%Y%m%d:%H:%M:%S', level=level)


def highest_power_of_2_below(n: int) -> int:
    p = int(math.log(n, 2))
    return int(pow(2, p))
