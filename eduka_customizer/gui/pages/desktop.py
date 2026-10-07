"""Desktop page: desktop environments, window managers and Eduka-Desktop."""

from eduka_customizer.qt.widgets import (QButtonGroup, QCheckBox, QFileDialog, QFormLayout, QGridLayout,
                             QLineEdit, QMessageBox, QTabWidget, QWidget)

from eduka_customizer.core import desktop as dsk
from eduka_customizer.core.config import settings
from eduka_customizer.core.eduka_desktop import CHOICES, EdukaDesktop
from eduka_customizer.gui.widgets import (Page, button, combo, hbox, label, tile, value_widget,
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
            b = tile("{}\n{}".format(d["name"], "Window manager" if d["kind"] == "wm" else "Desktop"),
                     d["description"] + "\n\nPackages: " + " ".join(d["packages"]))
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

        c = self.card("Login screen", "Pick the login screen (display manager and greeter).")
        grid = QGridLayout()
        grid.setSpacing(10)
        self.dm_group = QButtonGroup(self)
        self.dm_tiles = {}
        for i, d in enumerate(dsk.catalog()["display_managers"]):
            b = tile("{}\n{}".format(d["name"], d["description"]),
                     d["description"] + "\n\nPackages: " + " ".join(d["packages"]))
            self.dm_group.addButton(b)
            self.dm_tiles[d["id"]] = b
            grid.addWidget(b, i // 3, i % 3)
        c.add(grid)
        self.sddm_theme = combo([(t, t) for t, _p in dsk.catalog()["sddm_themes"]])
        c.add(hbox(button("Check availability", self.check_dms), None,
                   button("Use this login screen", self.set_dm, "primary")))
        c.add(hbox(label("SDDM theme"), self.sddm_theme, button("Apply SDDM theme", self.set_sddm_theme), None))
        self.current = label("", "muted")
        c.add(self.current)

        c = self.card("Session type and compositor",
                      "X11 is the most compatible (Eduka-Desktop needs it). Wayland is newer and smoother "
                      "on modern hardware. The compositor draws shadows, transparency and blur.")
        f = c.form()
        self.st_desktop = combo([(d["id"], d["name"]) for d in dsk.catalog()["desktops"]])
        self.st_desktop.currentIndexChanged.connect(self._session_types)
        self.st_type = combo([])
        f.addRow("Desktop:", self.st_desktop)
        f.addRow("Session type:", hbox(self.st_type, button("Apply session type", self.set_session_type)))
        self.comp = combo([])
        self.preset = combo([("shadows", "Shadows and fading"), ("light", "Light (fading only)"),
                             ("glass", "Glass (blur, needs OpenGL)"), ("off", "Effects off")])
        self.st_type.currentIndexChanged.connect(self._compositors)
        f.addRow("Compositor:", self.comp)
        f.addRow("Effects (picom):", hbox(self.preset, button("Apply compositor", self.set_compositor)))
        self.comp_desc = label("", "muted")
        self.comp.currentIndexChanged.connect(self._comp_desc)
        f.addRow("", self.comp_desc)
        self.session = combo([])
        f.addRow("Default session:", hbox(self.session, button("Set", self.set_session)))
        self.wm = combo(dsk.catalog()["window_managers_for_lxqt"])
        f.addRow("LXQt / Eduka window manager:", hbox(self.wm, button("Set", self.set_wm)))
        self._session_types()

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
        greeter = ""
        conf = rootfs / "etc/lightdm/lightdm.conf.d/50-edukasaun.conf"
        if conf.exists():
            import re
            m = re.search(r"greeter-session\s*=\s*(\S+)", conf.read_text())
            greeter = m.group(1) if m else ""
        for d in dsk.catalog()["display_managers"]:
            if d.get("service") == dm and (not d.get("greeter") or d.get("greeter") == greeter
                                           or (not greeter and d["id"] == "lightdm")):
                self.dm_tiles[d["id"]].setChecked(True)
                break
        for i in range(self.st_desktop.count()):
            if self.st_desktop.itemData(i) in installed:
                self.st_desktop.setCurrentIndex(i)
                break
        st = self.project.state.get("desktop", {})
        if st.get("session_type") and self.st_type.findData(st["session_type"]) >= 0:
            self.st_type.setCurrentIndex(self.st_type.findData(st["session_type"]))
        comp = st.get("compositor", {})
        if comp.get("id") and self.comp.findData(comp["id"]) >= 0:
            self.comp.setCurrentIndex(self.comp.findData(comp["id"]))
            self.preset.setCurrentIndex(max(0, self.preset.findData(comp.get("preset"))))
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

    def _dm_selected(self):
        for dm_id, b in self.dm_tiles.items():
            if b.isChecked():
                return dm_id
        return None

    def set_dm(self):
        dm = self._dm_selected()
        if not dm:
            QMessageBox.information(self, "Login screen", "Choose a login screen first.")
            return
        proj = self.project
        self.task("Set login screen", lambda t: dsk.DesktopManager(proj).set_display_manager(dm))

    def check_dms(self):
        proj = self.project
        dms = dsk.catalog()["display_managers"]

        def work(t):
            from eduka_customizer.core.apt import Packages
            pk = Packages(proj)
            with pk.chroot:
                pk.update()
                return pk.available(sorted({p for d in dms for p in d["packages"]}))

        def done(avail):
            for d in dms:
                ok = all(p in avail for p in d["packages"])
                b = self.dm_tiles[d["id"]]
                b.setEnabled(ok)
                if not ok:
                    b.setToolTip("Not available for this Debian suite")
        self.task("Check login screens", work, done)

    def set_sddm_theme(self):
        theme = self.sddm_theme.currentData()
        proj = self.project
        self.task("SDDM theme", lambda t: dsk.DesktopManager(proj).set_sddm_theme(theme))

    def _session_types(self):
        de = self.st_desktop.currentData()
        if not de:
            return
        types = dsk.desktop(de).get("sessions", {})
        self.st_type.clear()
        for kind, text in (("x11", "X11 (Xorg)"), ("wayland", "Wayland")):
            if kind in types:
                self.st_type.addItem(text, kind)
        self._compositors()

    def _compositors(self):
        kind = self.st_type.currentData() or "x11"
        self.comp.clear()
        for c in dsk.catalog()["compositors"]:
            if c["kind"] == kind:
                self.comp.addItem(c["name"], c["id"])
        self._comp_desc()

    def _comp_desc(self):
        cid = self.comp.currentData()
        for c in dsk.catalog()["compositors"]:
            if c["id"] == cid:
                self.comp_desc.setText(c["description"])

    def set_session_type(self):
        de, kind = self.st_desktop.currentData(), self.st_type.currentData()
        proj = self.project
        self.task("Session type", lambda t: dsk.DesktopManager(proj).set_session_type(de, kind))

    def set_compositor(self):
        cid, preset = self.comp.currentData(), self.preset.currentData()
        proj = self.project
        self.task("Compositor", lambda t: dsk.DesktopManager(proj).set_compositor(cid, preset))

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
