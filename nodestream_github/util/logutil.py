import logging
import os
import sys


def init_logger(name: str):
    logger = logging.getLogger(name)
    level = logging.getLevelName(os.environ.get("NODESTREAM_LOG_LEVEL", "INFO").upper())
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.handlers.append(handler)
    return logger
