import logging


def get_plugin_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.addHandler(logging.NullHandler())
    return logger
