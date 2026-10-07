"""Background tasks for the GUI: one long operation at a time."""

import logging
import traceback

from eduka_customizer.qt.core import QObject, QThread, pyqtSignal

from eduka_customizer.core import runner
from eduka_customizer.core.log import get_logger


class LogBridge(QObject):
    message = pyqtSignal(int, str)
    crashed = pyqtSignal(str)


class QtLogHandler(logging.Handler):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge

    def emit(self, record):
        try:
            self.bridge.message.emit(record.levelno, record.getMessage())
        except RuntimeError:
            pass


class Task(QThread):
    progress = pyqtSignal(float)
    stage = pyqtSignal(str)
    done = pyqtSignal(bool, object, str)

    def __init__(self, name, func, parent=None):
        super().__init__(parent)
        self.name = name
        self.func = func

    def run(self):
        runner.CANCEL.clear()
        try:
            result = self.func(self)
        except runner.Canceled as e:
            self.done.emit(False, None, str(e))
            return
        except Exception as e:  # report everything to the user
            get_logger().error("Task '%s' failed: %s\n%s", self.name, e, traceback.format_exc())
            self.done.emit(False, None, str(e) or e.__class__.__name__)
            return
        self.done.emit(True, result, "")

    # Callbacks usable from core code ----------------------------------
    def set_progress(self, pct):
        self.progress.emit(float(pct))

    def set_stage(self, text):
        get_logger().info("== %s ==", text)
        self.stage.emit(text)
