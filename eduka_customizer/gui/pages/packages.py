"""Packages page: search, install and remove Debian packages."""

from eduka_customizer.qt.widgets import (QAbstractItemView, QCheckBox, QFileDialog, QHeaderView, QLineEdit,
                             QListWidget, QMessageBox, QTableWidget, QTableWidgetItem)

from eduka_customizer.core.apt import Packages, read_package_list
from eduka_customizer.gui.widgets import Page, button, hbox, label


def table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
    t.setMinimumHeight(220)
    return t


def fill(t, rows):
    t.setRowCount(0)
    t.setSortingEnabled(False)
    for r, row in enumerate(rows):
        t.insertRow(r)
        for c, value in enumerate(row):
            t.setItem(r, c, QTableWidgetItem(str(value)))
    t.setSortingEnabled(True)
    t.resizeColumnToContents(0)


class PackagesPage(Page):
    title = "Packages"
    subtitle = "Install and remove Debian packages inside the image, or upgrade the whole system."
    icon_names = ("system-software-install", "package-x-generic")

    def build(self):
        c = self.card("Maintenance")
        c.add(hbox(button("Update lists", self.update_lists), button("Upgrade all", self.upgrade, "primary"),
                   button("Autoremove", self.autoremove), button("Install .deb files...", self.install_debs),
                   None))

        c = self.card("Find packages", "Searches the package lists of the image (apt-cache search).")
        self.query = QLineEdit()
        self.query.setPlaceholderText("e.g. gcompris, libreoffice, scratch, firmware ...")
        self.query.returnPressed.connect(self.search)
        c.add(hbox(self.query, button("Search", self.search, "primary")))
        self.results = table(["Package", "Description"])
        self.results.doubleClicked.connect(lambda _i: self.queue_install())
        c.add(self.results)
        c.add(hbox(None, button("Add to install list", self.queue_install)))

        a, b = self.row(self.card("To install"), self.card("To remove"))
        self.to_install = QListWidget()
        self.to_remove = QListWidget()
        for card, lst in ((a, self.to_install), (b, self.to_remove)):
            lst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            lst.setMinimumHeight(120)
            card.add(lst)
            card.add(hbox(None, button("Remove from list", lambda l=lst: self._drop(l))))
        self.add_name = QLineEdit()
        self.add_name.setPlaceholderText("package names, separated by spaces")
        self.add_name.returnPressed.connect(self.add_names)
        a.add(hbox(self.add_name, button("Add", self.add_names)))
        c = self.card()
        self.no_rec = QCheckBox("Do not install recommended packages (smaller image)")
        c.add(hbox(self.no_rec, None, button("Import list...", self.import_list),
                   button("Export list...", self.export_list),
                   button("Apply changes", self.apply, "primary")))

        c = self.card("Installed packages")
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter installed packages")
        self.filter.textChanged.connect(self.apply_filter)
        self.count = label("", "muted")
        c.add(hbox(self.filter, button("Reload", self.load_installed), self.count))
        self.installed = table(["Package", "Version", "Size (KiB)", "Description"])
        self.installed.setMinimumHeight(300)
        c.add(self.installed)
        c.add(hbox(None, button("Mark selected for removal", self.queue_remove, "danger")))

    def refresh(self):
        if self.project and self.installed.rowCount() == 0:
            self.load_installed()

    def project_changed(self):
        self.installed.setRowCount(0)
        self.results.setRowCount(0)
        self.to_install.clear()
        self.to_remove.clear()

    # Actions ---------------------------------------------------------------------
    def load_installed(self):
        rows = Packages(self.project).installed()
        fill(self.installed, rows)
        total = sum(int(r[2]) for r in rows if str(r[2]).isdigit())
        self.count.setText("{} packages, {:.1f} GiB".format(len(rows), total / 1024 ** 2))
        self.apply_filter(self.filter.text())

    def apply_filter(self, text):
        text = text.lower().strip()
        for r in range(self.installed.rowCount()):
            name = self.installed.item(r, 0).text().lower()
            desc = self.installed.item(r, 3).text().lower()
            self.installed.setRowHidden(r, bool(text) and text not in name and text not in desc)

    def search(self):
        term = self.query.text().strip()
        if not term:
            return
        proj = self.project
        self.task("Search packages", lambda t: Packages(proj).search(term), lambda rows: fill(self.results, rows))

    def _add(self, lst, names):
        have = {lst.item(i).text() for i in range(lst.count())}
        for n in names:
            if n and n not in have:
                lst.addItem(n)
                have.add(n)

    def _drop(self, lst):
        for it in lst.selectedItems():
            lst.takeItem(lst.row(it))

    def queue_install(self):
        rows = {i.row() for i in self.results.selectedIndexes()}
        self._add(self.to_install, [self.results.item(r, 0).text() for r in sorted(rows)])

    def queue_remove(self):
        rows = {i.row() for i in self.installed.selectedIndexes()}
        self._add(self.to_remove, [self.installed.item(r, 0).text() for r in sorted(rows)])

    def add_names(self):
        self._add(self.to_install, self.add_name.text().split())
        self.add_name.clear()

    def _items(self, lst):
        return [lst.item(i).text() for i in range(lst.count())]

    def apply(self):
        inst, rem = self._items(self.to_install), self._items(self.to_remove)
        if not inst and not rem:
            return
        msg = []
        if inst:
            msg.append("Install: " + " ".join(inst))
        if rem:
            msg.append("Remove: " + " ".join(rem))
        if QMessageBox.question(self, "Apply changes", "\n\n".join(msg)) != QMessageBox.StandardButton.Yes:
            return
        proj, no_rec = self.project, self.no_rec.isChecked()

        def work(t):
            pk = Packages(proj)
            with pk.chroot:
                if rem:
                    t.set_stage("Removing packages")
                    pk.remove(rem)
                if inst:
                    t.set_stage("Installing packages")
                    pk.install(inst, no_recommends=no_rec)

        def done(_):
            self.to_install.clear()
            self.to_remove.clear()
            self.load_installed()
        self.task("Apply package changes", work, done)

    def update_lists(self):
        proj = self.project
        self.task("Update package lists", lambda t: Packages(proj).update())

    def upgrade(self):
        proj = self.project
        self.task("Upgrade all packages", lambda t: Packages(proj).upgrade(), lambda _: self.load_installed())

    def autoremove(self):
        proj = self.project
        self.task("Autoremove", lambda t: Packages(proj).autoremove(), lambda _: self.load_installed())

    def install_debs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Install .deb packages", "", "Debian packages (*.deb)")
        if files:
            proj = self.project
            self.task("Install .deb files", lambda t: Packages(proj).install_debs(files),
                      lambda _: self.load_installed())

    def import_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import package list", "", "Text files (*.txt *.list);;All (*)")
        if path:
            inst, rem = read_package_list(path)
            self._add(self.to_install, inst)
            self._add(self.to_remove, rem)

    def export_list(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export package list", "packages.txt", "Text files (*.txt)")
        if path:
            lines = ["# Eduka-Customizer package list. '-name' means remove."]
            lines += self._items(self.to_install) + ["-" + n for n in self._items(self.to_remove)]
            with open(path, "w") as fh:
                fh.write("\n".join(lines) + "\n")
