# flake8: noqa
from disco.qt import API

if API == "PyQt6":
    from PyQt6.QtCore import *
else:
    from PyQt5.QtCore import *
