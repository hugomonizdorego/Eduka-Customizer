# flake8: noqa
from eduka_customizer.qt import API

if API == "PyQt6":
    from PyQt6.QtSvg import *
else:
    from PyQt5.QtSvg import *
