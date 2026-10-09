"""Qt binding selection: PyQt6 when available, PyQt5 otherwise.

PyQt5 (5.11+) accepts the scoped enum names used by PyQt6, so the GUI code
is written once for both. PyQt5 keeps DistroForge installable on older
Ubuntu releases that have no PyQt6.
"""

try:
    import PyQt6  # noqa: F401
    API = "PyQt6"
except ImportError:
    API = "PyQt5"


def version():
    if API == "PyQt6":
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    else:
        from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    return "{} {} (Qt {})".format(API, PYQT_VERSION_STR, QT_VERSION_STR)
