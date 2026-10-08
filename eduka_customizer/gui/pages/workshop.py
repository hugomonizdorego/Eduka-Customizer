"""Package Workshop page: edit installed Debian packages directly."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QMessageBox

from eduka_customizer.core.workshop import BRANDING_PACKAGES, Workshop
from eduka_customizer.gui.widgets import FileTreeEditor, Page, button, combo, hbox, label


class WorkshopPage(Page):
    title = "Package Workshop"
    nav_title = "Package Workshop"
    subtitle = ("Step 11 · For experts: open an installed Debian package, change its files, then rebuild and "
                "install it.")
    icon_names = ("package-x-generic", "applications-utilities", "document-edit")

    def build(self):
        c = self.card("Open a package")
        self.quick = combo([(p, "{}  —  {}".format(p, d)) for p, d in BRANDING_PACKAGES])
        c.add(hbox(label("Branding packages"), self.quick, button("Open", lambda: self.open(self.quick.currentData()),
                                                               "primary")))
        self.other = QLineEdit()
        self.other.setPlaceholderText("any installed package name, e.g. firefox-esr")
        self.other.returnPressed.connect(lambda: self.open(self.other.text().strip()))
        c.add(hbox(label("Other package"), self.other, button("Open", lambda: self.open(self.other.text().strip()))))
        self.opened = QListWidget()
        self.opened.setMaximumHeight(110)
        self.opened.currentItemChanged.connect(lambda cur, _prev: self.select(cur))
        c.add(label("Opened packages:", "muted"))
        c.add(self.opened)

        c = self.card("Edit")
        self.info = label("Open a package to edit it.", "muted")
        c.add(self.info)
        self.editor = FileTreeEditor("DEBIAN/ holds control, conffiles and maintainer scripts. "
                                     "Everything else is installed as is.")
        c.add(self.editor)

        c = self.card("Build")
        self.hold = QCheckBox("Hold the package (Debian updates will not replace it)")
        self.hold.setChecked(True)
        c.add(self.hold)
        c.add(label("Holding base-files also holds its security updates: re-open and rebuild the "
                    "package after Debian updates it, or use Distro Branding, which needs no hold.",
                    "muted"))
        c.add(hbox(button("Restore Debian version", self.restore, "danger"),
                   button("Close (discard edits)", self.close_pkg), None,
                   button("Build and install", self.build_pkg, "primary")))

    def _current(self):
        it = self.opened.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def refresh(self):
        if not self.project:
            return
        ws = Workshop(self.project)
        cur = self._current()
        self.opened.blockSignals(True)
        self.opened.clear()
        for name in ws.opened():
            info = self.project.state.get("workshop", {}).get(name, {})
            it = QListWidgetItem("{}   (Debian {}{})".format(name, info.get("original", "?"),
                                                           ", built " + info["version"] if info.get("version") else ""))
            it.setData(Qt.ItemDataRole.UserRole, name)
            self.opened.addItem(it)
            if name == cur:
                self.opened.setCurrentItem(it)
        self.opened.blockSignals(False)
        self.select(self.opened.currentItem())

    def select(self, item):
        if not item:
            self.editor.set_root(None)
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        ws = Workshop(self.project)
        ctrl = ws.control(name)
        self.info.setText("<b>{}</b> {} — {}".format(name, ctrl.get("Version", ""),
                                                     ctrl.get("Description", "").split("\n")[0]))
        self.editor.set_root(ws.path(name))

    def open(self, name):
        if not name:
            return
        proj = self.project
        self.task("Open package " + name, lambda t: Workshop(proj).open(name),
                  lambda _: self._select_name(name))

    def _select_name(self, name):
        self.refresh()
        for i in range(self.opened.count()):
            if self.opened.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.opened.setCurrentRow(i)

    def build_pkg(self):
        name = self._current()
        if not name:
            return
        self.editor.save()
        proj, hold = self.project, self.hold.isChecked()
        self.task("Build package " + name, lambda t: Workshop(proj).build(name, hold=hold))

    def restore(self):
        name = self._current()
        if name and QMessageBox.question(self, "Restore", "Reinstall Debian's version of {}?".format(name)) == \
                QMessageBox.StandardButton.Yes:
            proj = self.project
            self.task("Restore " + name, lambda t: Workshop(proj).restore(name))

    def close_pkg(self):
        name = self._current()
        if name:
            Workshop(self.project).close(name)
            self.refresh()
