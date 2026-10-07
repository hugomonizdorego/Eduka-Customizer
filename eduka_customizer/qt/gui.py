# flake8: noqa
from eduka_customizer.qt import API

if API == "PyQt6":
    from PyQt6.QtGui import *
else:
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import QAction  # moved to QtGui in Qt 6
    from PyQt5.QtWidgets import QFileSystemModel, QShortcut  # moved to QtGui in Qt 6
