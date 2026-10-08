"""Flatpak page: the Flathub catalog by category, install now or on first boot."""

import time

from eduka_customizer.qt.widgets import (QAbstractItemView, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                                          QMessageBox, QTableWidgetItem, QWidget)

from eduka_customizer.qt.core import Qt

from eduka_customizer.core import flathub
from eduka_customizer.core.flatpak import Flatpak, flathub_url, search_flathub
from eduka_customizer.gui.widgets import fill, table
from eduka_customizer.gui.widgets import Page, button, combo, hbox, label


class FlatpakPage(Page):
    title = "Flatpak apps"
    nav_title = "Flatpak apps"
    subtitle = ("Step 7 · Applications from Flathub by category. Install them into the ISO, or on the first "
                "start of an installed computer to keep the ISO small. Your changes wait in Review & Apply (step "
                "14).")
    icon_names = ("flatpak-discover", "applications-other", "system-software-update")
    CHANGES = ('Flatpak: ', 'Uninstall Flatpak apps')

    def build(self):
        c = self.card("Flathub")
        self.state = label("", "muted")
        c.add(hbox(self.state, None, button("Enable Flatpak + Flathub", self.setup, "primary")))

        c = self.card("Flathub applications",
                      "Every application of Flathub, by category, straight from flathub.org. Tick the ones you "
                      "want and press 'Add ticked apps'. 'Update from Flathub' fetches the newest catalog.")
        self.catalog_state = label("", "muted")
        c.add(hbox(self.catalog_state, None, button("Update from Flathub", self.update_catalog, "primary")))
        self.query = QLineEdit()
        self.query.setPlaceholderText("Filter by name or description (e.g. scratch, chemistry, music); Enter "
                                      "also searches flathub.org")
        self.query.textChanged.connect(lambda _t: self.show_category())
        self.query.returnPressed.connect(self.search)
        c.add(self.query)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        self.categories = QListWidget()
        self.categories.setFixedWidth(230)
        self.categories.setMinimumHeight(330)
        self.categories.currentRowChanged.connect(lambda _r: self.show_category())
        h.addWidget(self.categories)
        self.results = table(["Application", "Application ID", "Summary"])
        self.results.setMinimumHeight(330)
        self.results.doubleClicked.connect(lambda i: self._toggle(i.row()))
        h.addWidget(self.results, 1)
        c.add(row)
        c.add(hbox(button("Open on flathub.org", self.open_selected), None,
                   button("Add ticked apps", self.add_results, "primary")))
        self._apps = {}
        self._extra = {}

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
        if not self._apps:
            self.load_catalog()
        if not self._loaded and not self.main.task:
            self.load()

    def project_changed(self):
        self._loaded = False
        self._apps = {}
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

    # Catalog ------------------------------------------------------------------------
    def load_catalog(self):
        apps, info = flathub.Catalog(self.project).load()
        if apps:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(info["time"])) if info["time"] else "?"
            self.catalog_state.setText("{} applications from {} ({}).".format(len(apps), info["source"], when))
        else:
            apps = {a: {"name": n, "summary": s, "category": c} for a, n, s, c in flathub.FEATURED}
            self.catalog_state.setText("Showing a few well-known applications. Press 'Update from Flathub' for "
                                       "the whole catalog.")
        self._apps = apps
        counts = flathub.Catalog.counts(apps)
        current = self.categories.currentRow()
        self.categories.blockSignals(True)
        self.categories.clear()
        it = QListWidgetItem("All applications ({})".format(len(apps)))
        it.setData(Qt.ItemDataRole.UserRole, "")
        self.categories.addItem(it)
        for cid, title in flathub.CATEGORIES:
            it = QListWidgetItem("{} ({})".format(title, counts.get(cid, 0)))
            it.setData(Qt.ItemDataRole.UserRole, cid)
            self.categories.addItem(it)
        self.categories.setCurrentRow(current if current > 0 else 0)
        self.categories.blockSignals(False)
        self.show_category()

    def show_category(self):
        it = self.categories.currentItem()
        cat = it.data(Qt.ItemDataRole.UserRole) if it else ""
        apps = dict(self._apps, **self._extra)
        rows = flathub.Catalog.by_category(apps, cat or None, self.query.text())
        ticked = self._ticked()
        self.results.setSortingEnabled(False)
        self.results.setRowCount(0)
        for r, (app_id, name, summary, _c) in enumerate(rows[:2000]):
            self.results.insertRow(r)
            first = QTableWidgetItem(name)
            first.setFlags(first.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            first.setCheckState(Qt.CheckState.Checked if app_id in ticked else Qt.CheckState.Unchecked)
            first.setData(Qt.ItemDataRole.UserRole, app_id)
            self.results.setItem(r, 0, first)
            self.results.setItem(r, 1, QTableWidgetItem(app_id))
            self.results.setItem(r, 2, QTableWidgetItem(summary))
        self.results.resizeColumnToContents(0)
        self.results.resizeColumnToContents(1)

    def _ticked(self):
        out = set(getattr(self, "_ticks", set()))
        for r in range(self.results.rowCount()):
            it = self.results.item(r, 0)
            app_id = it.data(Qt.ItemDataRole.UserRole)
            if it.checkState() == Qt.CheckState.Checked:
                out.add(app_id)
            else:
                out.discard(app_id)
        self._ticks = out
        return out

    def _toggle(self, row):
        it = self.results.item(row, 0)
        if it:
            it.setCheckState(Qt.CheckState.Unchecked if it.checkState() == Qt.CheckState.Checked
                             else Qt.CheckState.Checked)

    def update_catalog(self):
        proj = self.project
        self.task("Update the Flathub catalog", lambda t: flathub.Catalog(proj).update(t.set_stage),
                  lambda _r: self.load_catalog())

    def open_selected(self):
        rows = sorted({i.row() for i in self.results.selectedIndexes()})
        if rows:
            import subprocess
            subprocess.Popen(["xdg-open", flathub_url(self.results.item(rows[0], 1).text())],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def add_results(self):
        ids = sorted(self._ticked())
        if not ids:
            QMessageBox.information(self, "Flatpak apps", "Tick the applications you want first.")
            return
        self._add(ids)
        self._ticks = set()
        self.show_category()

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
        def done(rows):
            for app_id, name, summary in rows:
                if app_id not in self._apps:
                    self._extra[app_id] = {"name": name, "summary": summary, "category": "Utility"}
            self.categories.setCurrentRow(0)
            self.show_category()
        self.task("Search Flathub", work, done)

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
