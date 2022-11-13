import logging


def init_logger(level=logging.DEBUG):
    # Line number : ":%(lineno)d"
    # TODO: set default to logging.INFO
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)-6s [%(filename)s] %(message)s',
                        datefmt='%Y%m%d:%H:%M:%S', level=level)
