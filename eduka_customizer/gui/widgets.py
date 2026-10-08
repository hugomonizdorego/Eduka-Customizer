"""Small reusable widgets that keep the pages short and consistent."""

from eduka_customizer.qt.core import Qt, pyqtSignal
from eduka_customizer.qt.gui import QIcon, QPixmap
from eduka_customizer.qt.widgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                                          QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                                          QPushButton, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout,
                                          QWidget)


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
        elif isinstance(item, QLabel) and item.wordWrap():
            # A wrapping text next to buttons takes the free room instead of a narrow column.
            lay.addWidget(item, 3)
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
        from eduka_customizer.qt.core import Qt as _Qt
        scroll.setHorizontalScrollBarPolicy(_Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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


TEXT_LIMIT = 2 << 20


class FileTreeEditor(QWidget):
    """Browse a folder, edit text files in place, add/replace/delete files."""

    def __init__(self, title_hint=""):
        from eduka_customizer.qt.gui import QFileSystemModel, QFont
        from eduka_customizer.qt.widgets import QPlainTextEdit, QSplitter, QTreeView
        super().__init__()
        self.root = None
        self.current = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter()
        self.model = QFileSystemModel()
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(260)
        self.tree.clicked.connect(self._open_index)
        split.addWidget(self.tree)
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("monospace"))
        self.editor.setPlaceholderText(title_hint or "Select a text file on the left to edit it.")
        self.editor.setMinimumHeight(300)
        split.addWidget(self.editor)
        split.setStretchFactor(1, 3)
        lay.addWidget(split)
        self.path_label = label("", "muted")
        lay.addWidget(self.path_label)
        lay.addWidget(hbox(button("New file...", self.new_file), button("Add / replace from disk...", self.add_file),
                           button("Delete", self.delete, "danger"), None,
                           button("Save file", self.save, "primary")))

    def set_root(self, path):
        from pathlib import Path
        self.root = Path(path) if path else None
        self.current = None
        self.editor.clear()
        if self.root and self.root.exists():
            idx = self.model.setRootPath(str(self.root))
            self.tree.setRootIndex(idx)
            self.setEnabled(True)
        else:
            self.setEnabled(False)

    def _selected_dir(self):
        from pathlib import Path
        idx = self.tree.currentIndex()
        if idx.isValid():
            p = Path(self.model.filePath(idx))
            return p if p.is_dir() else p.parent
        return self.root

    def _open_index(self, idx):
        from pathlib import Path
        p = Path(self.model.filePath(idx))
        if p.is_dir():
            return
        self.current = p
        self.path_label.setText(str(p.relative_to(self.root)) if self.root else str(p))
        try:
            if p.is_symlink():
                self.editor.setPlainText("(symbolic link to {})".format(p.readlink()))
                self.editor.setReadOnly(True)
                return
            data = p.read_bytes()[:TEXT_LIMIT]
            if b"\0" in data[:8192]:
                self.editor.setPlainText("(binary file, {} bytes) - use 'Add / replace from disk' "
                                         "to replace it".format(p.stat().st_size))
                self.editor.setReadOnly(True)
            else:
                self.editor.setPlainText(data.decode("utf-8", "replace"))
                self.editor.setReadOnly(False)
        except OSError as e:
            self.editor.setPlainText(str(e))

    def save(self):
        if self.current and not self.editor.isReadOnly():
            self.current.write_text(self.editor.toPlainText())
            self.path_label.setText("Saved " + str(self.current.relative_to(self.root)))

    def new_file(self):
        from eduka_customizer.qt.widgets import QInputDialog
        base = self._selected_dir()
        if not base:
            return
        name, ok = QInputDialog.getText(self, "New file", "Name (sub/folders/allowed):")
        if ok and name and ".." not in name.split("/"):
            p = base / name.strip("/")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()

    def add_file(self):
        import shutil
        base = self._selected_dir()
        files, _ = QFileDialog.getOpenFileNames(self, "Add files", "")
        for f in files:
            if self.current and len(files) == 1 and self.current.parent == base \
                    and QMessageBox.question(self, "Replace", "Replace {} with {}?".format(
                        self.current.name, f)) == QMessageBox.StandardButton.Yes:
                shutil.copy2(f, self.current)
            else:
                shutil.copy2(f, base / f.split("/")[-1])

    def delete(self):
        import shutil
        idx = self.tree.currentIndex()
        if not idx.isValid():
            return
        from pathlib import Path
        p = Path(self.model.filePath(idx))
        if p == self.root or QMessageBox.question(self, "Delete", "Delete {}?".format(p.name)) != \
                QMessageBox.StandardButton.Yes:
            return
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
        self.current = None
        self.editor.clear()


def tile(text, tooltip=""):
    """A checkable card-like button that may shrink with the window."""
    b = QPushButton(text)
    b.setObjectName("tile")
    b.setCheckable(True)
    b.setMinimumHeight(58)
    b.setMinimumWidth(120)
    b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    if tooltip:
        b.setToolTip(tooltip)
    return b


class DropZone(QFrame):
    """Drop files, folders or archives here, or use the buttons; emits the paths."""

    dropped = pyqtSignal(list)

    def __init__(self, text, file_filter="All files (*)", folders=True):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.file_filter = file_filter
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        buttons = [None, button("Add files...", self._files)]
        if folders:
            buttons.append(button("Add folder...", self._folder))
        lay.addWidget(hbox(*buttons, None))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hover", True)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("hover", False)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("hover", False)
        self.style().polish(self)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.dropped.emit(paths)

    def _files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add files", "", self.file_filter)
        if files:
            self.dropped.emit(files)

    def _folder(self):
        d = QFileDialog.getExistingDirectory(self, "Add folder")
        if d:
            self.dropped.emit([d])


def table(headers):
    """A read-only table with a stretching last column."""
    from eduka_customizer.qt.widgets import QAbstractItemView, QHeaderView, QTableWidget
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
    t.setMinimumHeight(220)
    return t


def fill(t, rows):
    from eduka_customizer.qt.widgets import QTableWidgetItem
    t.setRowCount(0)
    t.setSortingEnabled(False)
    for r, row in enumerate(rows):
        t.insertRow(r)
        for c, value in enumerate(row):
            t.setItem(r, c, QTableWidgetItem(str(value)))
    t.setSortingEnabled(True)
    t.resizeColumnToContents(0)
