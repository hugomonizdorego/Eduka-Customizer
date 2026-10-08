"""Repositories page: Debian suite presets and a sources file editor."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.gui import QFont
from eduka_customizer.qt.widgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QInputDialog,
                             QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QSplitter)

from eduka_customizer.core.apt import Packages, Sources, debian_sources, format_deb822
from eduka_customizer.core.config import settings
from eduka_customizer.gui.widgets import FilePicker, Page, button, combo, hbox, label


class RepoDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add repository")
        f = QFormLayout(self)
        self.name = QLineEdit()
        self.name.setPlaceholderText("myrepo")
        self.uri = QLineEdit()
        self.uri.setPlaceholderText("https://repo.example.org/debian")
        self.suites = QLineEdit()
        self.suites.setPlaceholderText("trixie")
        self.components = QLineEdit("main")
        self.key = FilePicker("Repository key", "Keys (*.gpg *.asc *.key);;All files (*)")
        self.key.edit.setPlaceholderText("URL or file of the signing key (recommended)")
        for text, w in (("Name:", self.name), ("URI:", self.uri), ("Suites:", self.suites),
                        ("Components:", self.components), ("Signing key:", self.key)):
            f.addRow(text, w)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class SourcesPage(Page):
    title = "Repositories"
    subtitle = ("Edit sources.list and sources.list.d. Choose the Debian suite the image follows: "
                "stable, testing or sid.")
    icon_names = ("software-properties", "preferences-system-network", "network-server")

    def build(self):
        c = self.card("Debian suite", "Writes a clean deb822 file "
                                      "/etc/apt/sources.list.d/debian.sources. Old Debian entries are "
                                      "kept as *.eduka-old.")
        f = c.form()
        self.suite = combo([("stable", "Stable"), ("testing", "Testing"), ("sid", "Sid (unstable)")])
        f.addRow("Suite:", self.suite)
        self.mirror = QLineEdit(settings().get("debian", "mirror"))
        f.addRow("Mirror:", self.mirror)
        self.components = QLineEdit(settings().get("debian", "components"))
        f.addRow("Components:", self.components)
        self.codename = QCheckBox("Use codename (trixie) instead of alias (stable) - avoids surprise "
                                  "major upgrades")
        self.codename.setChecked(True)
        f.addRow("", self.codename)
        self.security = QCheckBox("Security updates")
        self.security.setChecked(True)
        self.updates = QCheckBox("Stable updates")
        self.updates.setChecked(True)
        self.backports = QCheckBox("Backports (stable only)")
        self.debsrc = QCheckBox("Source packages (deb-src)")
        f.addRow("", hbox(self.security, self.updates, self.backports, self.debsrc, None))
        c.add(hbox(button("Preview", self.preview), None,
                   button("Apply and update", self.apply_suite, "primary")))
        c.add(label("Switching an image to a newer suite needs 'Upgrade all' on the Packages page.",
                    "muted"))

        c = self.card("Source files")
        split = QSplitter()
        self.files = QListWidget()
        self.files.setMinimumWidth(220)
        self.files.currentTextChanged.connect(self.load_file)
        split.addWidget(self.files)
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("monospace"))
        self.editor.setMinimumHeight(260)
        split.addWidget(self.editor)
        split.setStretchFactor(1, 3)
        c.add(split)
        c.add(hbox(button("New file", self.new_file), button("Add repository...", self.add_repo),
                   button("Delete file", self.delete_file, "danger"), None,
                   button("Save", self.save_file), button("Save and apt update", self.save_update, "primary")))

    def refresh(self):
        if not self.project:
            return
        d = self.project.distro
        idx = self.suite.findData(d.suite)
        if idx >= 0:
            self.suite.setCurrentIndex(idx)
        current = self.files.currentItem().text() if self.files.currentItem() else ""
        self.files.blockSignals(True)
        self.files.clear()
        for p in Sources(self.project.rootfs).files():
            self.files.addItem(p.name)
        self.files.blockSignals(False)
        items = self.files.findItems(current or "debian.sources", Qt.MatchFlag.MatchExactly)
        if items:
            self.files.setCurrentItem(items[0])
        elif self.files.count():
            self.files.setCurrentRow(0)

    def _stanzas(self):
        return debian_sources(self.suite.currentData(), mirror=self.mirror.text().strip() or None,
                              components=self.components.text().strip() or None,
                              updates=self.updates.isChecked(), security=self.security.isChecked(),
                              backports=self.backports.isChecked(), deb_src=self.debsrc.isChecked(),
                              use_codename=self.codename.isChecked())

    def preview(self):
        QMessageBox.information(self, "debian.sources", format_deb822(self._stanzas()))

    def apply_suite(self):
        suite = self.suite.currentData()
        if suite != self.project.distro.suite:
            r = QMessageBox.question(self, "Change suite",
                                     "The image is {} and you selected {}. After applying, run "
                                     "'Upgrade all' on the Packages page. Moving back to an older "
                                     "suite is not supported by APT. Continue?".format(
                                         self.project.distro.suite, suite))
            if r != QMessageBox.StandardButton.Yes:
                return
        stanzas = self._stanzas()
        proj = self.project

        def work(t):
            src = Sources(proj.rootfs)
            src.set_debian(suite)
            src.write("debian.sources", format_deb822(stanzas))
            Packages(proj).update()
            proj.record("sources", suite)
        self.task("Set Debian {} sources".format(suite), work)

    def load_file(self, name):
        if name and self.project:
            self.editor.setPlainText(Sources(self.project.rootfs).read(name))

    def _current(self):
        it = self.files.currentItem()
        return it.text() if it else None

    def save_file(self):
        name = self._current()
        if not name:
            return False
        try:
            Sources(self.project.rootfs).write(name, self.editor.toPlainText())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid file", str(e))
            return False
        return True

    def save_update(self):
        if self.save_file():
            proj = self.project
            self.task("apt update", lambda t: Packages(proj).update())

    def new_file(self):
        name, ok = QInputDialog.getText(self, "New sources file", "File name (ends with .sources or .list):",
                                        text="custom.sources")
        if ok and name:
            try:
                Sources(self.project.rootfs).write(name, "# Types: deb\n# URIs: \n# Suites: \n# Components: main\n")
            except ValueError as e:
                QMessageBox.warning(self, "Invalid name", str(e))
            self.refresh()

    def delete_file(self):
        name = self._current()
        if name and QMessageBox.question(self, "Delete", "Delete {}?".format(name)) == QMessageBox.StandardButton.Yes:
            Sources(self.project.rootfs).delete(name)
            self.refresh()

    def add_repo(self):
        dlg = RepoDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        proj = self.project
        args = (dlg.name.text().strip(), dlg.uri.text().strip(), dlg.suites.text().strip(),
                dlg.components.text().strip(), dlg.key.text() or None)
        if not all(args[:3]):
            QMessageBox.warning(self, "Add repository", "Name, URI and suites are required.")
            return

        def work(t):
            Sources(proj.rootfs).add_repository(*args)
            Packages(proj).update()
            proj.record("repository", args[1])
        self.task("Add repository " + args[0], work)
