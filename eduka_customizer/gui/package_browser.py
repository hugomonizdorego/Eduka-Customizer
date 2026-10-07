"""Browse every package of the image's Debian sources: search as you type, tick
to install, untick installed ones to remove; and the image's own applications."""

from eduka_customizer.qt.core import QAbstractTableModel, QModelIndex, Qt, QTimer, pyqtSignal
from eduka_customizer.qt.gui import QBrush, QColor
from eduka_customizer.qt.widgets import QHeaderView, QLineEdit, QTableView, QVBoxLayout, QWidget

from eduka_customizer.core.catalog import Catalog, is_app
from eduka_customizer.gui.widgets import combo, hbox, label

COLUMNS = ["Package", "Version", "Section", "Size (KiB)", "Description"]
GREEN = QColor("#00875f")
RED = QColor("#c0392b")


class PackageModel(QAbstractTableModel):
    """Rows are dicts; only the visible (filtered) rows are shown."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.rows = []       # every package
        self.visible = []    # indexes into rows
        self.checked = set()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.visible)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        r = self.rows[self.visible[index.row()]]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (r["name"], r["version"], r["section"], r["size"], r["description"])[col]
        if role == Qt.ItemDataRole.CheckStateRole and col == 0:
            return Qt.CheckState.Checked if r["name"] in self.checked else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.ForegroundRole:
            ticked = r["name"] in self.checked
            if ticked != r["installed"]:
                return QBrush(GREEN if ticked else RED)
            if r["installed"]:
                return QBrush(GREEN)
        if role == Qt.ItemDataRole.ToolTipRole and r["protected"]:
            return "Needed by the system: cannot be removed here"
        return None

    def flags(self, index):
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            f |= Qt.ItemFlag.ItemIsUserCheckable
        return f

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.CheckStateRole or index.column() != 0:
            return False
        r = self.rows[self.visible[index.row()]]
        on = int(getattr(value, "value", value)) == 2  # Qt.CheckState.Checked (PyQt5 and PyQt6)
        if not on and r["protected"]:
            return False  # removing an essential package would break the system
        (self.checked.add if on else self.checked.discard)(r["name"])
        self.dataChanged.emit(index, self.index(index.row(), len(COLUMNS) - 1))
        self.changed.emit()
        return True

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.checked = {r["name"] for r in rows if r["installed"]}
        self.visible = list(range(len(rows)))
        self.endResetModel()

    def filter(self, words, section, show):
        self.beginResetModel()
        out = []
        for i, r in enumerate(self.rows):
            if show == "apps" and not r["app"]:
                continue
            if show == "installed" and not r["installed"]:
                continue
            if show == "changes" and (r["name"] in self.checked) == r["installed"]:
                continue
            if section and r["section"] != section:
                continue
            if words and not all(w in r["hay"] for w in words):
                continue
            out.append(i)
        self.visible = out
        self.endResetModel()


class PackageBrowser(QWidget):
    """Load with load(rootfs); read the choice with changes() -> (install, remove)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name or description, e.g. gcompris, office, paint, chemistry ...")
        self.search.setClearButtonEnabled(True)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._apply_filter)
        self.search.textChanged.connect(lambda _t: self.timer.start(200))
        self.show_combo = combo([("apps", "Applications"), ("all", "All packages"),
                                 ("installed", "Installed"), ("changes", "My changes")])
        self.show_combo.currentIndexChanged.connect(self._apply_filter)
        self.section = combo([("", "All sections")])
        self.section.currentIndexChanged.connect(self._apply_filter)
        lay.addWidget(hbox(self.search, self.show_combo, self.section))
        self.model = PackageModel()
        self.model.changed.connect(self._update_summary)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.verticalHeader().setVisible(False)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.setMinimumHeight(340)
        self.view.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for col, width in ((0, 240), (1, 150), (2, 90), (3, 80)):
            self.view.setColumnWidth(col, width)
        lay.addWidget(self.view)
        self.summary = label("", "muted")
        lay.addWidget(self.summary)

    def load(self, rootfs):
        cat = Catalog(rootfs)
        avail, installed = cat.available(), cat.installed()
        rows, sections = [], set()
        for name in sorted(set(avail) | set(installed)):
            info = avail.get(name) or installed.get(name)
            inst = installed.get(name, {})
            section = info.get("section", "")
            sections.add(section)
            desc = info.get("description", "")
            rows.append({"name": name, "version": inst.get("version") or info.get("version", ""),
                         "section": section, "size": int(info.get("size", 0)), "description": desc,
                         "installed": bool(inst), "app": is_app(name, section), "hay": (name + " " + desc).lower(),
                         "protected": bool(inst) and (inst.get("essential") or
                                                      inst.get("priority") in ("required", "important"))})
        self.model.set_rows(rows)
        keep = self.section.currentData()
        self.section.blockSignals(True)
        self.section.clear()
        self.section.addItem("All sections", "")
        for s in sorted(x for x in sections if x):
            self.section.addItem(s, s)
        self.section.setCurrentIndex(max(0, self.section.findData(keep)))
        self.section.blockSignals(False)
        self._apply_filter()
        if not avail:
            self.summary.setText("No package lists in the image yet: press 'Refresh package lists' (needs internet).")
        return len(avail)

    def _apply_filter(self):
        self.model.filter([w for w in self.search.text().lower().split() if w], self.section.currentData() or "",
                          self.show_combo.currentData())
        self._update_summary()

    def _update_summary(self):
        if not self.model.rows:
            return
        inst, rem = self.changes()

        def short(names):
            return " ".join(names[:10]) + (" … (+{})".format(len(names) - 10) if len(names) > 10 else "") or "none"
        self.summary.setText("{} of {} shown · to install: {} · to remove: {}".format(
            len(self.model.visible), len(self.model.rows), short(inst), short(rem)))

    def changes(self):
        install = sorted(r["name"] for r in self.model.rows if r["name"] in self.model.checked and not r["installed"])
        remove = sorted(r["name"] for r in self.model.rows if r["name"] not in self.model.checked and r["installed"])
        return install, remove

    def select(self, names):
        known = {r["name"] for r in self.model.rows}
        self.model.checked |= {n for n in names if n in known}
        self._apply_filter()

    def reset(self):
        self.model.checked = {r["name"] for r in self.model.rows if r["installed"]}
        self._apply_filter()


class AppRemover(QWidget):
    """The applications installed in the image, tick the ones to remove."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from eduka_customizer.qt.widgets import QListWidget
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setMinimumHeight(200)
        lay.addWidget(self.list)
        self.note = label("", "muted")
        lay.addWidget(self.note)

    def load(self, rootfs):
        from eduka_customizer.qt.widgets import QListWidgetItem
        self.list.clear()
        apps = Catalog(rootfs).desktop_apps()
        for a in apps:
            it = QListWidgetItem("{} — {}{}".format(a["name"], a["package"],
                                                    "  (needed by the system)" if a["protected"] else ""))
            it.setData(Qt.ItemDataRole.UserRole, a["package"])
            it.setToolTip(a["comment"])
            if a["protected"]:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(it)
        self.note.setText("{} applications in the image. Tick the ones the ISO should not contain.".format(len(apps))
                          if apps else "No applications found in the image.")

    def selected(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.flags() & Qt.ItemFlag.ItemIsUserCheckable and it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out
