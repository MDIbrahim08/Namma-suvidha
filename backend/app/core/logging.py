"""Basic structured (key=value) logging setup."""

import logging
import sys

LOG_FORMAT = "time=%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

