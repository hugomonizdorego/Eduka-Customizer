"""Replace apps page: swap the default programs of the desktop (browser, mail, office,
editor, file manager, terminal, viewers, players, ...) for the ones you prefer."""

from eduka_customizer.qt.widgets import QCheckBox, QMessageBox

from eduka_customizer.core import replace
from eduka_customizer.gui.widgets import Page, button, combo, fill, hbox, label, table


class ReplaceAppsPage(Page):
    title = "Replace default applications"
    nav_title = "Replace apps"
    subtitle = ("Step 7 · Use another browser, mail program, office suite, editor, file manager, terminal or "
                "player. The new one becomes the default for every user; the old one can be removed. Your "
                "changes wait in Review & Apply (step 14).")
    icon_names = ("preferences-desktop-default-applications", "applications-other")
    CHANGES = ('Replace ',)

    def build(self):
        c = self.card("Default applications of the image")
        self.table = table(["Kind", "Installed now", "Default for its files"])
        c.add(self.table)
        c.add(hbox(None, button("Reload", self.reload)))

        c = self.card("Replace", "Pick the kind, then the program that should do the job. You can type any "
                                 "Debian package name too.")
        f = c.form()
        self.role = combo([(r["id"], r["name"]) for r in replace.roles()])
        self.role.currentIndexChanged.connect(lambda _i: self._role_changed())
        f.addRow("Kind:", self.role)
        self.new = combo([], editable=True)
        f.addRow("New program:", self.new)
        self.remove_old = QCheckBox("Remove the programs of this kind that are installed now")
        f.addRow("", self.remove_old)
        self.note = label("", "muted")
        f.addRow("", self.note)
        f.addRow("", label("✔ <b>Applies to everyone</b>: the default for every user of the live session and of "
                           "every computer installed from the ISO, in every desktop (file types, Debian "
                           "alternatives, Xfce, KDE, LXQt, GNOME, Cinnamon and MATE settings).", "muted"))
        c.add(hbox(None, button("Replace for everyone", self.apply, "primary")))
        self._status = []
        self._role_changed()

    def refresh(self):
        if self.project:
            self.reload()

    def reload(self):
        self._status = replace.status(self.project.rootfs)
        fill(self.table, [(r["name"], " ".join(r["installed"]) or "—", r["default"] or "—") for r in self._status])
        self.table.sortItems(0)
        self.table.resizeColumnToContents(1)
        self._role_changed()

    def _current(self):
        return next((r for r in self._status if r["role"] == self.role.currentData()), None)

    def _role_changed(self):
        r = replace.role(self.role.currentData())
        st = self._current()
        installed = st["installed"] if st else []
        self.new.clear()
        for pkg in r["candidates"]:
            self.new.addItem(pkg + ("  (installed)" if pkg in installed else ""), pkg)
        self.note.setText("Installed now: {}".format(" ".join(installed) or "none of the known programs"))

    def apply(self):
        role_id = self.role.currentData()
        idx = self.new.currentIndex()
        text = self.new.currentText().split()[0] if self.new.currentText().strip() else ""
        new = self.new.itemData(idx) if idx >= 0 and self.new.itemText(idx) == self.new.currentText() else text
        if not new:
            return
        st = self._current()
        remove = [p for p in (st["installed"] if st else []) if p != new] if self.remove_old.isChecked() else []
        msg = "Make {} the default {} for everyone (all users)?".format(new, replace.role(role_id)["name"].lower())
        if remove:
            msg += "\n\nRemove: " + " ".join(remove)
        if QMessageBox.question(self, "Replace application", msg) != QMessageBox.StandardButton.Yes:
            return
        proj = self.project
        self.task("Replace " + replace.role(role_id)["name"].lower(),
                  lambda t: replace.Replacer(proj).replace(role_id, new, remove, t.set_stage),
                  lambda _r: self.reload())
