"""Small reusable widgets that keep the pages short and consistent."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                             QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                             QSizePolicy, QSpinBox, QVBoxLayout, QWidget)


def icon(*names):
    for n in names:
        ic = QIcon.fromTheme(n)
        if not ic.isNull():
            return ic
    return QIcon()


def button(text, slot=None, kind=None, icon_names=(), tooltip=""):
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    if icon_names:
        b.setIcon(icon(*icon_names))
    if tooltip:
        b.setToolTip(tooltip)
    if slot:
        b.clicked.connect(lambda _=False: slot())
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def label(text, kind=None, wrap=True):
    lab = QLabel(text)
    if kind:
        lab.setObjectName(kind)
    lab.setWordWrap(wrap)
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lab


def hbox(*widgets, stretch_at=None, margins=0, spacing=8):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(margins, margins, margins, margins)
    lay.setSpacing(spacing)
    for i, item in enumerate(widgets):
        if i == stretch_at:
            lay.addStretch(1)
        if item is None:
            lay.addStretch(1)
        elif isinstance(item, QWidget):
            lay.addWidget(item)
        else:
            lay.addLayout(item)
    if stretch_at is not None and stretch_at >= len(widgets):
        lay.addStretch(1)
    return w


class Card(QFrame):
    """A rounded white panel with a title, an optional subtitle and a body."""

    def __init__(self, title="", subtitle="", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(10)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        if title:
            t = QLabel(title)
            t.setObjectName("cardTitle")
            self.body.addWidget(t)
        if subtitle:
            self.body.addWidget(label(subtitle, "muted"))

    def add(self, widget):
        if isinstance(widget, QWidget):
            self.body.addWidget(widget)
        else:
            self.body.addLayout(widget)
        return widget

    def form(self):
        f = QFormLayout()
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        f.setHorizontalSpacing(14)
        f.setVerticalSpacing(8)
        self.body.addLayout(f)
        return f


class Page(QWidget):
    """Base class of every page in the sidebar."""

    title = ""
    subtitle = ""
    icon_names = ()
    needs_rootfs = True

    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        inner = QWidget()
        inner.setObjectName("pageArea")
        scroll.setWidget(inner)
        self.layout_ = QVBoxLayout(inner)
        self.layout_.setContentsMargins(28, 22, 28, 22)
        self.layout_.setSpacing(14)
        head = QLabel(self.title)
        head.setObjectName("pageTitle")
        self.layout_.addWidget(head)
        if self.subtitle:
            self.layout_.addWidget(label(self.subtitle, "pageSubtitle"))
        self.build()
        self.layout_.addStretch(1)

    # Helpers --------------------------------------------------------------
    @property
    def project(self):
        return self.main.project

    def add(self, widget):
        self.layout_.addWidget(widget)
        return widget

    def card(self, title="", subtitle=""):
        return self.add(Card(title, subtitle))

    def row(self, *cards):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        for c in cards:
            lay.addWidget(c, 1)
        self.layout_.addWidget(w)
        return cards

    def task(self, name, func, done=None):
        return self.main.run_task(name, func, done)

    def build(self):
        pass

    def refresh(self):
        """Called whenever the page is shown or the project changed."""


class FilePicker(QWidget):
    changed = pyqtSignal(str)

    def __init__(self, caption="Choose file", filter_="All files (*)", directory=False, save=False):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.textChanged.connect(self.changed.emit)
        lay.addWidget(self.edit, 1)
        lay.addWidget(button("Browse...", self.browse))
        self.caption, self.filter, self.directory, self.save = caption, filter_, directory, save

    def browse(self):
        start = self.edit.text() or ""
        if self.directory:
            path = QFileDialog.getExistingDirectory(self, self.caption, start)
        elif self.save:
            path, _ = QFileDialog.getSaveFileName(self, self.caption, start, self.filter)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self.caption, start, self.filter)
        if path:
            self.edit.setText(path)

    def text(self):
        return self.edit.text().strip()

    def setText(self, text):
        self.edit.setText(text)


class ImagePreview(QLabel):
    def __init__(self, w=220, h=124):
        super().__init__()
        self.setFixedSize(w, h)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("badge")
        self.setText("No image")

    def show_file(self, path):
        pix = QPixmap(path) if path else QPixmap()
        if pix.isNull():
            self.setPixmap(QPixmap())
            self.setText("No image")
            return
        self.setPixmap(pix.scaled(self.width() - 6, self.height() - 6,
                                  Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation))


def combo(items, current=None, editable=False):
    c = QComboBox()
    c.setEditable(editable)
    for it in items:
        if isinstance(it, (tuple, list)):
            c.addItem(str(it[1]), it[0])
        else:
            c.addItem(str(it), it)
    if current is not None:
        idx = c.findData(current)
        if idx < 0:
            idx = c.findText(str(current))
        if idx >= 0:
            c.setCurrentIndex(idx)
        elif editable:
            c.setEditText(str(current))
    c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return c


def value_widget(value, choices=None):
    """Create an editor matching the type of *value* (for generic settings)."""
    if choices:
        return combo(choices, value, editable=False)
    if isinstance(value, bool):
        w = QCheckBox()
        w.setChecked(value)
        return w
    if isinstance(value, int):
        w = QSpinBox()
        w.setRange(-10000, 10000)
        w.setValue(value)
        return w
    if isinstance(value, float):
        w = QDoubleSpinBox()
        w.setRange(0, 1000)
        w.setDecimals(2)
        w.setSingleStep(0.05 if value <= 1 else 1)
        w.setValue(value)
        return w
    w = QLineEdit(str(value))
    return w


def widget_value(w, original):
    if isinstance(w, QCheckBox):
        return w.isChecked()
    if isinstance(w, (QSpinBox, QDoubleSpinBox)):
        return w.value()
    if isinstance(w, QComboBox):
        return w.currentData() if w.currentData() is not None else w.currentText()
    text = w.text()
    return type(original)(text) if isinstance(original, (int, float)) and text else text
