"""Users page: the live user (name, password or no password, autologin) and
accounts created inside the image."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QInputDialog, QLineEdit, QMessageBox, QTreeWidget,
                                          QTreeWidgetItem)

from eduka_customizer.core import users as usr
from eduka_customizer.gui.widgets import Page, button, combo, hbox, label


def password_field(placeholder):
    e = QLineEdit()
    e.setEchoMode(QLineEdit.EchoMode.Password)
    e.setPlaceholderText(placeholder)
    return e


class UsersPage(Page):
    title = "Users and Passwords"
    nav_title = "Users"
    subtitle = ("Step 4 · The user of the live session (with a password, without one, or Debian's default) and "
                "accounts that every installed computer gets. Your changes wait in Review & Apply (step 14).")
    icon_names = ("system-users", "user-identity", "preferences-system-users")
    CHANGES = ('Change password of ', 'Create account ', 'Delete account ', 'Remove password of ', 'Save live user')

    def build(self):
        c = self.card("Live user", "Created every time the ISO boots. Debian's default is the user "
                                   "'user' with the password 'live'.")
        f = c.form()
        self.live_name = QLineEdit()
        self.live_name.setPlaceholderText("live")
        f.addRow("User name:", self.live_name)
        self.live_full = QLineEdit()
        f.addRow("Full name:", self.live_full)
        self.live_mode = combo(list(usr.PASSWORD_MODES.items()))
        self.live_mode.currentIndexChanged.connect(self._mode_changed)
        f.addRow("Password:", self.live_mode)
        self.live_pw = password_field("new password")
        self.live_pw2 = password_field("repeat the password")
        f.addRow("", hbox(self.live_pw, self.live_pw2))
        self.live_auto = QCheckBox("Log in automatically when the ISO starts")
        f.addRow("", self.live_auto)
        self.live_groups = QLineEdit()
        f.addRow("Groups:", self.live_groups)
        self.live_state = label("", "muted")
        c.add(self.live_state)
        c.add(hbox(button("Remove (back to Debian's user/live)", self.remove_live, "danger"), None,
                   button("Save live user", self.save_live, "primary")))

        c = self.card("Accounts in the image",
                      "Real accounts inside the system, for example an administrator account. "
                      "They exist in the live session and on every computer installed from this ISO.")
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["User", "Full name", "Password", "Groups", "Home"])
        self.tree.setRootIsDecorated(False)
        self.tree.setMinimumHeight(150)
        c.add(self.tree)
        c.add(hbox(button("Delete account", self.delete_account, "danger"),
                   button("Remove password", self.remove_password), None,
                   button("Change password...", self.change_password)))

        c = self.card("New account")
        f = c.form()
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("lower-case letters, e.g. admin")
        f.addRow("User name:", self.new_name)
        self.new_full = QLineEdit()
        f.addRow("Full name:", self.new_full)
        self.new_nopw = QCheckBox("No password (log in without a password)")
        self.new_nopw.toggled.connect(lambda on: (self.new_pw.setEnabled(not on), self.new_pw2.setEnabled(not on)))
        self.new_pw = password_field("password")
        self.new_pw2 = password_field("repeat the password")
        f.addRow("Password:", hbox(self.new_pw, self.new_pw2))
        f.addRow("", self.new_nopw)
        self.new_admin = QCheckBox("Administrator (member of 'sudo')")
        f.addRow("", self.new_admin)
        self.new_shell = combo(["/bin/bash", "/bin/sh", "/usr/bin/zsh", "/usr/bin/fish"])
        f.addRow("Shell:", self.new_shell)
        c.add(hbox(None, button("Create account", self.add_account, "primary")))

    # Helpers -----------------------------------------------------------------------
    def users(self):
        return usr.Users(self.project)

    def _mode_changed(self):
        custom = self.live_mode.currentData() == "custom"
        self.live_pw.setEnabled(custom)
        self.live_pw2.setEnabled(custom)

    def _selected(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.ItemDataRole.UserRole) if it else None

    def refresh(self):
        if not self.project:
            return
        u = self.users()
        live = u.live()
        # Not configured yet: suggest "live" / "Live" (the ISO still uses Debian's "user").
        name, full = (live["username"], live["fullname"]) if live["configured"] else usr.SUGGESTED_USER
        self.live_name.setText(name)
        self.live_full.setText(full)
        self.live_mode.setCurrentIndex(max(0, self.live_mode.findData(live["password"])))
        self.live_pw.clear()
        self.live_pw2.clear()
        self._mode_changed()
        self.live_auto.setChecked(live["autologin"])
        self.live_groups.setText(" ".join(live["groups"]))
        self.live_state.setText(
            "Live user: <b>{}</b> — {}{}".format(live["username"], usr.PASSWORD_MODES[live["password"]],
                                                 "" if live["configured"] else " (Debian defaults, not set yet)"))
        keep = self._selected()
        self.tree.clear()
        for a in u.accounts():
            it = QTreeWidgetItem([a["username"], a["fullname"], a["password"], " ".join(a["groups"]), a["home"]])
            it.setData(0, Qt.ItemDataRole.UserRole, a["username"])
            self.tree.addTopLevelItem(it)
            if a["username"] == keep:
                self.tree.setCurrentItem(it)
        for i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(i)

    def _passwords_match(self, a, b):
        if a.text() != b.text():
            QMessageBox.warning(self, "Password", "The two passwords are not the same.")
            return False
        return True

    # Actions -------------------------------------------------------------------------
    def save_live(self):
        mode = self.live_mode.currentData()
        if mode == "custom":
            if not self.live_pw.text():
                QMessageBox.information(self, "Password", "Type the password twice, or choose another option.")
                return
            if not self._passwords_match(self.live_pw, self.live_pw2):
                return
        try:
            usr.check_username(self.live_name.text().strip())
        except ValueError as e:
            QMessageBox.warning(self, "User name", str(e))
            return
        proj = self.project
        kw = dict(username=self.live_name.text().strip(), fullname=self.live_full.text().strip(),
                  password_mode=mode, password=self.live_pw.text(), autologin=self.live_auto.isChecked(),
                  groups=self.live_groups.text().split())
        self.live_pw.clear()
        self.live_pw2.clear()
        self.task("Save live user", lambda t: usr.Users(proj).set_live(**kw), lambda _r: self.refresh())

    def remove_live(self):
        if QMessageBox.question(self, "Live user", "Remove the live user settings? The ISO then starts "
                                "with Debian's user 'user' and the password 'live'.") != \
                QMessageBox.StandardButton.Yes:
            return
        self.users().remove_live()
        self.refresh()

    def add_account(self):
        name = self.new_name.text().strip()
        try:
            usr.check_username(name)
        except ValueError as e:
            QMessageBox.warning(self, "User name", str(e))
            return
        password = None
        if not self.new_nopw.isChecked():
            if not self.new_pw.text():
                QMessageBox.information(self, "Password", "Type a password twice, or tick 'No password'.")
                return
            if not self._passwords_match(self.new_pw, self.new_pw2):
                return
            password = self.new_pw.text()
        proj = self.project
        kw = dict(username=name, fullname=self.new_full.text().strip(), password=password,
                  admin=self.new_admin.isChecked(), shell=self.new_shell.currentText())
        self.new_pw.clear()
        self.new_pw2.clear()

        def done(_r):
            self.new_name.clear()
            self.new_full.clear()
            self.refresh()
        self.task("Create account " + name, lambda t: usr.Users(proj).add_account(**kw), done)

    def change_password(self):
        name = self._selected()
        if not name:
            return
        first, ok = QInputDialog.getText(self, "Password", "New password for {}:".format(name),
                                         QLineEdit.EchoMode.Password)
        if not ok or not first:
            return
        second, ok = QInputDialog.getText(self, "Password", "Repeat the password:", QLineEdit.EchoMode.Password)
        if not ok:
            return
        if first != second:
            QMessageBox.warning(self, "Password", "The two passwords are not the same.")
            return
        proj = self.project
        self.task("Change password of " + name, lambda t: usr.Users(proj).set_password(name, first),
                  lambda _r: self.refresh())

    def remove_password(self):
        name = self._selected()
        if name and QMessageBox.question(self, "Remove password", "{} will log in without a password. "
                                         "Continue?".format(name)) == QMessageBox.StandardButton.Yes:
            proj = self.project
            self.task("Remove password of " + name, lambda t: usr.Users(proj).set_password(name, None),
                      lambda _r: self.refresh())

    def delete_account(self):
        name = self._selected()
        if name and QMessageBox.question(self, "Delete account", "Delete the account {} and its home "
                                         "folder from the image?".format(name)) == QMessageBox.StandardButton.Yes:
            proj = self.project
            self.task("Delete account " + name, lambda t: usr.Users(proj).delete_account(name),
                      lambda _r: self.refresh())
