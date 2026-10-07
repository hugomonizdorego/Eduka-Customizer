# flake8: noqa
from eduka_customizer.qt import API

if API == "PyQt6":
    from PyQt6.QtWidgets import *
else:
    from PyQt5.QtWidgets import *
