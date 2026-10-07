"""Flatpak page: Flathub setup, search, install now or on first boot."""

from PyQt6.QtWidgets import QAbstractItemView, QLineEdit, QListWidget, QListWidgetItem, QMessageBox

from PyQt6.QtCore import Qt

from eduka_customizer.core.flatpak import EDUCATION_PICKS, Flatpak, search_flathub
from eduka_customizer.gui.pages.packages import fill, table
from eduka_customizer.gui.widgets import Page, button, combo, hbox, label


class FlatpakPage(Page):
    title = "Flatpak apps"
    subtitle = ("Add applications from Flathub (flathub.org). Install them into the ISO now, or "
                "only on the first boot of the installed system to keep the ISO small.")
    icon_names = ("flatpak-discover", "applications-other", "system-software-update")

    def build(self):
        c = self.card("Flathub")
        self.state = label("", "muted")
        c.add(hbox(self.state, None, button("Enable Flatpak + Flathub", self.setup, "primary")))

        c = self.card("Recommended for schools", "Tick the apps you want, then press Add.")
        self.picks = QListWidget()
        self.picks.setMinimumHeight(180)
        for app_id, name, summary in EDUCATION_PICKS:
            it = QListWidgetItem("{}  —  {}  ({})".format(name, summary, app_id))
            it.setData(Qt.ItemDataRole.UserRole, app_id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.picks.addItem(it)
        c.add(self.picks)
        c.add(hbox(None, button("Add ticked apps", self.add_picks)))

        c = self.card("Search Flathub")
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search applications (e.g. scratch, chemistry, music)")
        self.query.returnPressed.connect(self.search)
        c.add(hbox(self.query, button("Search", self.search, "primary")))
        self.results = table(["Application ID", "Name", "Summary"])
        self.results.doubleClicked.connect(lambda _i: self.add_results())
        c.add(self.results)
        c.add(hbox(None, button("Add selected", self.add_results)))

        c = self.card("Selected apps")
        self.selected = QListWidget()
        self.selected.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.selected.setMinimumHeight(110)
        c.add(self.selected)
        self.mode = combo([("now", "Install into the ISO now"),
                           ("firstboot", "Install on first boot of the installed system")])
        c.add(hbox(button("Remove from list", self.drop), None, self.mode,
                   button("Apply", self.apply, "primary")))

        c = self.card("Installed in the image")
        self.installed = table(["Application ID", "Name", "Version", "Size"])
        self.installed.setMinimumHeight(160)
        c.add(self.installed)
        self.firstboot = label("", "muted")
        c.add(self.firstboot)
        c.add(hbox(button("Reload", self.load), None, button("Uninstall selected", self.uninstall, "danger")))

    _loaded = False

    def refresh(self):
        if not self.project:
            return
        fp = Flatpak(self.project)
        self.state.setText("Flatpak is installed in the image." if fp.available()
                           else "Flatpak is not installed in the image yet.")
        fb = fp.firstboot_list()
        self.firstboot.setText("Installed on first boot: " + (", ".join(fb) if fb else "none"))
        if not self._loaded and not self.main.task:
            self.load()

    def project_changed(self):
        self._loaded = False
        self.installed.setRowCount(0)

    def load(self):
        self._loaded = True
        proj = self.project
        if Flatpak(proj).available():
            self.task("List Flatpak apps", lambda t: Flatpak(proj).installed(),
                      lambda rows: fill(self.installed, rows))

    def _add(self, ids):
        have = {self.selected.item(i).text() for i in range(self.selected.count())}
        for i in ids:
            if i not in have:
                self.selected.addItem(i)

    def add_picks(self):
        ids = []
        for i in range(self.picks.count()):
            it = self.picks.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                ids.append(it.data(Qt.ItemDataRole.UserRole))
                it.setCheckState(Qt.CheckState.Unchecked)
        self._add(ids)

    def add_results(self):
        rows = sorted({i.row() for i in self.results.selectedIndexes()})
        self._add([self.results.item(r, 0).text() for r in rows])

    def drop(self):
        for it in self.selected.selectedItems():
            self.selected.takeItem(self.selected.row(it))

    def search(self):
        term = self.query.text().strip()
        if not term:
            return
        proj = self.project

        def work(t):
            try:
                return search_flathub(term)
            except OSError as e:
                t.set_stage("Flathub API unreachable ({}), searching inside the image".format(e))
                return Flatpak(proj).search(term)
        self.task("Search Flathub", work, lambda rows: fill(self.results, rows))

    def setup(self):
        proj = self.project
        self.task("Enable Flatpak and Flathub", lambda t: Flatpak(proj).setup(),
                  lambda _: setattr(self, "_loaded", False))

    def apply(self):
        ids = [self.selected.item(i).text() for i in range(self.selected.count())]
        if not ids:
            return
        proj, mode = self.project, self.mode.currentData()

        def work(t):
            fp = Flatpak(proj)
            if mode == "firstboot":
                fp.set_firstboot(sorted(set(fp.firstboot_list() + ids)))
            else:
                fp.install(ids)
        def done(_):
            self.selected.clear()
            self._loaded = False
        self.task("Flatpak: " + ("first boot list" if mode == "firstboot" else "install"), work, done)

    def uninstall(self):
        rows = sorted({i.row() for i in self.installed.selectedIndexes()})
        ids = [self.installed.item(r, 0).text() for r in rows]
        if not ids:
            fb = Flatpak(self.project).firstboot_list()
            if fb and QMessageBox.question(self, "First boot", "Clear the first-boot list?") == \
                    QMessageBox.StandardButton.Yes:
                Flatpak(self.project).set_firstboot([])
                self.refresh()
            return
        proj = self.project
        self.task("Uninstall Flatpak apps", lambda t: Flatpak(proj).uninstall(ids),
                  lambda _: setattr(self, "_loaded", False))
