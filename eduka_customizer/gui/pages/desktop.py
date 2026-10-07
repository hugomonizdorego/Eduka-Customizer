"""Desktop page: desktop environments, window managers and Eduka-Desktop."""

from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QFormLayout, QGridLayout,
                             QLineEdit, QMessageBox, QPushButton, QTabWidget, QWidget)

from eduka_customizer.core import desktop as dsk
from eduka_customizer.core.config import settings
from eduka_customizer.core.eduka_desktop import CHOICES, EdukaDesktop
from eduka_customizer.gui.widgets import (Page, button, combo, hbox, label, value_widget,
                                          widget_value)

HIDDEN_KEYS = {"menu_icon", "_settings_revision", "locked", "reserve_workarea",
               "force_window_above_panel"}


class DesktopPage(Page):
    title = "Desktop"
    subtitle = ("Build the desktop: Eduka-Desktop (default for Edukasaun OS), another desktop "
                "environment or a window manager. Choose the login manager and default session.")
    icon_names = ("preferences-desktop", "user-desktop", "video-display")

    def build(self):
        c = self.card("Desktop environment or window manager")
        grid = QGridLayout()
        grid.setSpacing(10)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tiles = {}
        for i, d in enumerate(dsk.catalog()["desktops"]):
            b = QPushButton("{}\n{}".format(d["name"], "Window manager" if d["kind"] == "wm" else "Desktop"))
            b.setObjectName("tile")
            b.setCheckable(True)
            b.setToolTip(d["description"] + "\n\nPackages: " + " ".join(d["packages"]))
            b.setMinimumHeight(58)
            self.group.addButton(b)
            self.tiles[d["id"]] = b
            grid.addWidget(b, i // 4, i % 4)
        self.tiles["eduka"].setChecked(True)
        c.add(grid)
        self.desc = label("", "muted")
        self.group.buttonToggled.connect(lambda *_: self._describe())
        c.add(self.desc)
        f = c.form()
        self.dm_for_install = combo([("", "Keep current / recommended")] +
                                    [(d["id"], d["name"]) for d in dsk.catalog()["display_managers"]])
        f.addRow("Login manager:", self.dm_for_install)
        self.remove_others = QCheckBox("Remove other Debian desktop tasks (task-*-desktop)")
        f.addRow("", self.remove_others)
        self.no_rec = QCheckBox("Minimal install (no recommended packages)")
        f.addRow("", self.no_rec)
        c.add(hbox(None, button("Install selected desktop", self.install, "primary")))

        c = self.card("Session and login manager", "What starts after login and in the live session.")
        f = c.form()
        self.session = combo([])
        f.addRow("Default session:", hbox(self.session, button("Set", self.set_session)))
        self.dm = combo([(d["id"], d["name"]) for d in dsk.catalog()["display_managers"]])
        f.addRow("Login manager:", hbox(self.dm, button("Set", self.set_dm)))
        self.wm = combo(dsk.catalog()["window_managers_for_lxqt"])
        f.addRow("LXQt / Eduka window manager:", hbox(self.wm, button("Set", self.set_wm)))
        self.current = label("", "muted")
        c.add(self.current)

        c = self.card("Eduka-Desktop", "Eduka-Panel, Eduka-Menu and Eduka-Menu-Settings, built from "
                                       "git into a .deb and installed into the image.")
        f = c.form()
        self.repo = QLineEdit(settings().get("edukasaun", "eduka_desktop_repo"))
        f.addRow("Git repository or folder:", self.repo)
        self.ref = QLineEdit(settings().get("edukasaun", "eduka_desktop_ref"))
        self.ref.setPlaceholderText("default branch")
        f.addRow("Branch / tag:", self.ref)
        self.ed_state = label("", "muted")
        f.addRow("Status:", self.ed_state)
        c.add(hbox(button("Choose local folder...", self.choose_folder), None,
                   button("Build .deb only", self.build_deb), button("Install .deb...", self.install_deb),
                   button("Fetch, build and install", self.ed_install, "primary")))

        c = self.card("Eduka-Desktop defaults for new users",
                      "Stored in /etc/skel/.config/eduka-desktop and copied to the live user and "
                      "every user created after installation. Fields follow the installed "
                      "Eduka-Desktop version.")
        self.tabs = QTabWidget()
        c.add(self.tabs)
        self.forms = {}
        c.add(hbox(None, button("Save defaults", self.save_defaults, "primary")))
        self._describe()

    def _describe(self):
        for de_id, b in self.tiles.items():
            if b.isChecked():
                d = dsk.desktop(de_id)
                self.desc.setText("<b>{}</b>: {}".format(d["name"], d["description"]))

    def _selected(self):
        for de_id, b in self.tiles.items():
            if b.isChecked():
                return de_id
        return "eduka"

    def refresh(self):
        if not self.project:
            return
        rootfs = self.project.rootfs
        installed = set(dsk.installed_desktops(rootfs))
        for de_id, b in self.tiles.items():
            d = dsk.desktop(de_id)
            b.setText("{}{}\n{}".format(d["name"], "  ✓" if de_id in installed else "",
                                         "Window manager" if d["kind"] == "wm" else "Desktop"))
        sessions = dsk.sessions(rootfs)
        self.session.clear()
        for s in sessions:
            self.session.addItem("{} ({})".format(s["name"], s["type"]), s["id"])
        cur = self.project.state.get("desktop", {}).get("session")
        if cur and self.session.findData(cur) >= 0:
            self.session.setCurrentIndex(self.session.findData(cur))
        dm = dsk.detect_display_manager(rootfs)
        if self.dm.findData(dm) >= 0:
            self.dm.setCurrentIndex(self.dm.findData(dm))
        self.current.setText("Login manager in the image: {}  ·  default session: {}".format(
            dm or "none", cur or "not set"))
        ed = EdukaDesktop(self.project)
        iv = ed.installed_version()
        sv = ed.source_version() if ed.src.exists() else ""
        info = self.project.state.get("eduka_desktop", {})
        self.ed_state.setText("Installed: {}   ·   Source: {} {}".format(
            iv or "not installed", sv or "not fetched", ("(" + info.get("commit", "") + ")") if info.get("commit") else ""))
        self._build_forms(ed)

    def _build_forms(self, ed):
        self.tabs.clear()
        self.forms = {}
        current = ed.current_defaults()
        if not any(current.values()):
            w = QWidget()
            lay = QFormLayout(w)
            lay.addRow(label("Install or fetch Eduka-Desktop first to edit its defaults.", "muted"))
            self.tabs.addTab(w, "Eduka-Desktop")
            return
        for section, title in (("panel", "Eduka-Panel"), ("desktop", "Eduka-Menu (desktop)"),
                               ("menu", "Menu")):
            values = current.get(section, {})
            w = QWidget()
            lay = QFormLayout(w)
            editors = {}
            for key, value in values.items():
                if key in HIDDEN_KEYS or isinstance(value, (list, dict)) or value is None:
                    continue
                ed_w = value_widget(value, CHOICES.get(key))
                editors[key] = (ed_w, value)
                lay.addRow(key.replace("_", " ").capitalize() + ":", ed_w)
            self.forms[section] = editors
            self.tabs.addTab(w, title)

    # Actions -------------------------------------------------------------------
    def install(self):
        de_id = self._selected()
        d = dsk.desktop(de_id)
        if QMessageBox.question(self, "Install desktop", "Install {} into the image?\n\nPackages: {}"
                                .format(d["name"], " ".join(d["packages"]))) != QMessageBox.StandardButton.Yes:
            return
        proj = self.project
        dm, rem, no_rec = self.dm_for_install.currentData() or None, self.remove_others.isChecked(), self.no_rec.isChecked()
        self.task("Install " + d["name"],
                  lambda t: dsk.DesktopManager(proj).install(de_id, dm_id=dm, remove_others=rem,
                                                             no_recommends=no_rec))

    def set_session(self):
        sid = self.session.currentData()
        if sid:
            proj = self.project
            self.task("Set default session", lambda t: dsk.DesktopManager(proj).set_default_session(sid))

    def set_dm(self):
        dm = self.dm.currentData()
        proj = self.project
        self.task("Set login manager", lambda t: dsk.DesktopManager(proj).set_display_manager(dm))

    def set_wm(self):
        dsk.DesktopManager(self.project).set_lxqt_window_manager(self.wm.currentData())
        self.refresh()

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Eduka-Desktop source folder")
        if d:
            self.repo.setText(d)

    def _src(self):
        return self.repo.text().strip() or None, self.ref.text().strip()

    def build_deb(self):
        proj = self.project
        repo, ref = self._src()

        def work(t):
            ed = EdukaDesktop(proj)
            ed.fetch(repo, ref)
            return ed.build()
        self.task("Build Eduka-Desktop", work,
                  lambda deb: QMessageBox.information(self, "Eduka-Desktop", "Built:\n{}".format(deb)))

    def ed_install(self):
        proj = self.project
        repo, ref = self._src()
        self.task("Install Eduka-Desktop", lambda t: EdukaDesktop(proj).fetch_build_install(repo, ref))

    def install_deb(self):
        path, _ = QFileDialog.getOpenFileName(self, "Eduka-Desktop package", "", "Debian packages (*.deb)")
        if path:
            proj = self.project
            self.task("Install Eduka-Desktop .deb", lambda t: EdukaDesktop(proj).install(path))

    def save_defaults(self):
        if not self.forms:
            return
        values = {}
        for section, editors in self.forms.items():
            values[section] = {k: widget_value(w, orig) for k, (w, orig) in editors.items()}
        EdukaDesktop(self.project).write_defaults(values.get("panel"), values.get("menu"),
                                                  values.get("desktop"))
        self.main.stage_label.setText("Eduka-Desktop defaults saved to /etc/skel")
