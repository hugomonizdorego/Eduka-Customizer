"""Logging helpers shared by the CLI and the GUI."""

import logging
import sys

LOGGER_NAME = "eduka"

_COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}
_RESET = "\033[0m"

# Log level used for raw command output so the GUI can show it dimmed.
OUTPUT = 15
logging.addLevelName(OUTPUT, "OUTPUT")


class _ConsoleFormatter(logging.Formatter):
    def __init__(self, color):
        super().__init__()
        self.color = color

    def format(self, record):
        msg = record.getMessage()
        if record.levelno == OUTPUT:
            return "    " + msg
        prefix = {logging.DEBUG: "D", logging.INFO: "*", logging.WARNING: "!",
                  logging.ERROR: "E", logging.CRITICAL: "E"}.get(record.levelno, "*")
        if self.color:
            return "{}{}{} {}".format(_COLORS.get(record.levelno, ""), prefix, _RESET, msg)
        return "{} {}".format(prefix, msg)


def get_logger():
    return logging.getLogger(LOGGER_NAME)


def setup_console(debug=False):
    logger = get_logger()
    logger.setLevel(logging.DEBUG if debug else OUTPUT)
    if not any(getattr(h, "_eduka_console", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler._eduka_console = True
        handler.setFormatter(_ConsoleFormatter(sys.stderr.isatty()))
        logger.addHandler(handler)
    return logger


def add_file_handler(path):
    """Mirror every message into a project log file."""
    logger = get_logger()
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename == str(path):
            return h
    handler = logging.FileHandler(str(path), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return handler


def remove_handler(handler):
    get_logger().removeHandler(handler)
    handler.close()


log = get_logger()
