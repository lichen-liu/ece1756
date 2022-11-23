from ram_mapper import driver
from ram_mapper.utils import init_logger


def init(parser):
    driver.init(parser)


def run(args):
    driver.run(args)
