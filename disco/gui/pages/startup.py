"""Startup: what starts by itself in the distribution, switched on or off with a tick."""

from disco.qt.core import Qt
from disco.qt.widgets import QLineEdit, QMessageBox, QTreeWidget, QTreeWidgetItem

from disco.core import startup
from disco.gui.widgets import Page, button, hbox, label


class StartupPage(Page):
    title = "Startup"
    nav_title = "Startup"
    subtitle = ("What starts by itself: services that start with the system, and programs that start after a user "
                "logs in. Tick what should start, untick what should not. Your changes wait in Review & Apply.")
    icon_names = ("preferences-system-startup", "system-run", "preferences-system")
    CHANGES = ("Startup:",)

    def build(self):
        c = self.card("Services (start with the system)",
                      "🔒 marks services the system needs to start: they stay on. Turning off what you do not need "
                      "makes the system start faster.")
        self.services = QTreeWidget()
        self.services.setHeaderLabels(["Service", "What it does"])
        self.services.setColumnWidth(0, 300)
        self.services.setMinimumHeight(260)
        self.services.setRootIsDecorated(False)
        c.add(self.services)
        c.add(hbox(label("", "muted"), None, button("Reload", self.refresh),
                   button("Apply the ticks", self.apply_services, "primary")))

        a = self.card("Programs after login",
                      "Programs every user's desktop starts after logging in (/etc/xdg/autostart).")
        self.apps = QTreeWidget()
        self.apps.setHeaderLabels(["Program", "Command", "Where"])
        self.apps.setColumnWidth(0, 260)
        self.apps.setColumnWidth(1, 300)
        self.apps.setMinimumHeight(200)
        self.apps.setRootIsDecorated(False)
        a.add(self.apps)
        a.add(hbox(button("Remove the selected program", self.remove_app, "danger"), None,
                   button("Apply the ticks", self.apply_apps, "primary")))

        n = self.card("Add a program to start after login", "For example a welcome page in the browser, a chat "
                                                           "program or a script of yours.")
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("Name, for example Welcome page")
        self.new_cmd = QLineEdit()
        self.new_cmd.setPlaceholderText("Command, for example firefox-esr https://example.org")
        n.add(hbox(self.new_name, self.new_cmd, button("Add", self.add_app, "primary")))
        self._services = []
        self._apps = []

    def refresh(self):
        if not self.project or not self.project.has_rootfs():
            return
        self._services = startup.services(self.project)
        self.services.clear()
        for s in self._services:
            it = QTreeWidgetItem([("🔒 " if s["essential"] else "") + s["unit"], s["description"]])
            it.setData(0, Qt.ItemDataRole.UserRole, s["unit"])
            flags = it.flags() | Qt.ItemFlag.ItemIsUserCheckable
            if s["essential"] and s["enabled"]:
                flags &= ~Qt.ItemFlag.ItemIsEnabled
            it.setFlags(flags)
            it.setCheckState(0, Qt.CheckState.Checked if s["enabled"] else Qt.CheckState.Unchecked)
            self.services.addTopLevelItem(it)
        self._apps = startup.applications(self.project)
        self.apps.clear()
        for app in self._apps:
            it = QTreeWidgetItem([app["name"], app["exec"], app["where"] or "every desktop"])
            it.setToolTip(0, app["comment"] or app["file"])
            it.setData(0, Qt.ItemDataRole.UserRole, app["file"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked if app["enabled"] else Qt.CheckState.Unchecked)
            self.apps.addTopLevelItem(it)
        if not self._apps:
            it = QTreeWidgetItem(["No programs start after login yet", "", ""])
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.apps.addTopLevelItem(it)

    def _changed(self, tree, items, key):
        out = []
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            ident = it.data(0, Qt.ItemDataRole.UserRole)
            if not ident:
                continue
            on = it.checkState(0) == Qt.CheckState.Checked
            old = next((x for x in items if x[key] == ident), None)
            if old is not None and old["enabled"] != on:
                out.append((ident, on))
        return out

    def apply_services(self):
        changes = self._changed(self.services, self._services, "unit")
        if not changes:
            self.main.stage_label.setText("No service was changed")
            return
        proj = self.project
        for unit, on in changes:
            self.task("Startup: service {} {}".format(unit, "on" if on else "off"),
                      lambda t, u=unit, o=on: startup.set_service(proj, u, o))

    def apply_apps(self):
        changes = self._changed(self.apps, self._apps, "file")
        if not changes:
            self.main.stage_label.setText("No program was changed")
            return
        proj = self.project
        for file, on in changes:
            self.task("Startup: program {} {}".format(file, "on" if on else "off"),
                      lambda t, f=file, o=on: startup.set_application(proj, f, o))

    def add_app(self):
        name, cmd = self.new_name.text().strip(), self.new_cmd.text().strip()
        if not name or not cmd:
            QMessageBox.information(self, "Startup", "Type a name and the command to start.")
            return
        proj = self.project
        self.task("Startup: add {}".format(name), lambda t: startup.add_application(proj, name, cmd))
        self.new_name.clear()
        self.new_cmd.clear()

    def remove_app(self):
        it = self.apps.currentItem()
        file = it.data(0, Qt.ItemDataRole.UserRole) if it else None
        if not file:
            return
        if not file.startswith("disco-"):
            QMessageBox.information(self, "Startup", "Only programs added here can be removed. Untick the others to "
                                    "switch them off.")
            return
        proj = self.project
        self.task("Startup: remove {}".format(file), lambda t: startup.remove_application(proj, file))
