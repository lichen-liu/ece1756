import logging

logger = logging.getLogger('ram_mapper')
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d %(levelname)-7s [%(filename)s] %(message)s', datefmt='%m%d:%H:%M:%S'))
logger.addHandler(_handler)


def init_logger(level=logging.INFO):
    logger.setLevel(level)


def verbosity_to_logging_level(verbose_count: int, quiet: bool) -> int:
    if quiet:
        return logging.ERROR
    if verbose_count == 0:
        return logging.WARNING
    elif verbose_count == 1:
        return logging.INFO
    else:
        return logging.DEBUG
