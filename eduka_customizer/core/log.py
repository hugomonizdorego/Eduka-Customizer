"""Logging helpers shared by the CLI and the GUI."""

import logging
import logging.handlers
import os
import platform
import sys
import threading
import traceback

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
    logger.setLevel(logging.DEBUG)
    if not any(getattr(h, "_eduka_console", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG if debug else OUTPUT)
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


# Developer logs: every run writes here so crashes can be reported and fixed.
DEBUG_DIR = os.environ.get("DISTROFORGE_LOG_DIR") or os.environ.get("EDUKA_CUSTOMIZER_LOG_DIR") or "/tmp/distroforge"
DEBUG_LOG = os.path.join(DEBUG_DIR, "distroforge.log")
ERROR_LOG = os.path.join(DEBUG_DIR, "errors.log")
_debug_ready = False


def setup_debug_log(component="cli"):
    """Log everything to /tmp/distroforge/ and catch unhandled errors.

    distroforge.log       full debug log (rotated, 5 MiB x 3)
    errors.log            errors and tracebacks only
    """
    global _debug_ready, DEBUG_DIR, DEBUG_LOG, ERROR_LOG
    if _debug_ready:
        return DEBUG_DIR
    try:
        DEBUG_DIR = _safe_dir(DEBUG_DIR)
        DEBUG_LOG = os.path.join(DEBUG_DIR, "distroforge.log")
        ERROR_LOG = os.path.join(DEBUG_DIR, "errors.log")
        for path in (DEBUG_LOG, ERROR_LOG):
            if os.path.islink(path):
                os.unlink(path)
        logger = get_logger()
        logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(process)d %(threadName)s] %(levelname)s "
                                "%(module)s:%(lineno)d %(message)s")
        full = logging.handlers.RotatingFileHandler(DEBUG_LOG, maxBytes=5 << 20, backupCount=3,
                                                    encoding="utf-8")
        full.setLevel(logging.DEBUG)
        full.setFormatter(fmt)
        errors = logging.handlers.RotatingFileHandler(ERROR_LOG, maxBytes=2 << 20, backupCount=2,
                                                      encoding="utf-8")
        errors.setLevel(logging.ERROR)
        errors.setFormatter(fmt)
        logger.addHandler(full)
        logger.addHandler(errors)
        for path in (DEBUG_LOG, ERROR_LOG):
            try:
                os.chmod(path, 0o666)
            except OSError:
                pass
    except OSError as e:
        sys.stderr.write("Cannot write logs to {}: {}\n".format(DEBUG_DIR, e))
        return None
    _debug_ready = True
    from eduka_customizer import VERSION
    logger.debug("===== DistroForge %s %s started: %s", VERSION, component, " ".join(sys.argv))
    logger.debug("Python %s on %s, uid %s", platform.python_version(), platform.platform(), os.geteuid())
    try:
        with open("/etc/os-release") as fh:
            host = [l.split("=", 1)[1].strip().strip('"') for l in fh if l.startswith("PRETTY_NAME=")]
        logger.debug("Host: %s", host[0] if host else "unknown")
    except OSError:
        pass
    sys.excepthook = _excepthook
    threading.excepthook = lambda a: _excepthook(a.exc_type, a.exc_value, a.exc_traceback)
    return DEBUG_DIR


def _safe_dir(path):
    """Create the log folder; never trust one planted by another user."""
    try:
        os.mkdir(path)
        os.chmod(path, 0o1777)  # shared by root (pkexec) and the developer
        return path
    except FileExistsError:
        pass
    st = os.lstat(path)
    import stat
    if stat.S_ISDIR(st.st_mode) and st.st_uid in (0, os.geteuid()):
        return path
    alt = "{}-{}".format(path, os.geteuid())
    os.makedirs(alt, mode=0o755, exist_ok=True)
    st = os.lstat(alt)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        raise OSError("unsafe log directory {}".format(alt))
    return alt


def _excepthook(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    get_logger().critical("Unhandled error: %s\n%s", exc,
                          "".join(traceback.format_exception(exc_type, exc, tb)))
    for hook in list(_error_listeners):
        try:
            hook(exc_type, exc, tb)
        except Exception:
            pass


_error_listeners = []


def on_unhandled_error(callback):
    """Register a callback (the GUI shows a dialog)."""
    _error_listeners.append(callback)


log = get_logger()
