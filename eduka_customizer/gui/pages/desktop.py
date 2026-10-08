"""Desktop page: one choice for the desktop environment or window manager (Eduka-Desktop
included), and its login screen, session type and compositor, which follow it."""

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
    nav_title = "Desktop"
    subtitle = ("Step 6 · Choose a desktop environment or window manager and how complete it is (Mini, Compact, "
                "Full, Full with apps), then the login screen, X11 or Wayland and the compositor. Your changes "
                "wait in Review & Apply (step 12).")
    icon_names = ("preferences-desktop", "user-desktop", "video-display")
    CHANGES = ("Set up desktop", "Install Eduka-Desktop")

    def build(self):
        c = self.card("1. Desktop environment or window manager")
        grid = QGridLayout()
        grid.setSpacing(10)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tiles = {}
        for i, d in enumerate(dsk.catalog()["desktops"]):
            b = tile("{}\n{}".format(d["name"], "Window manager" if d["kind"] == "wm" else "Desktop"),
                     d["description"] + ("\n\n" + d["note"] if d.get("note") else ""))
            self.group.addButton(b)
            self.tiles[d["id"]] = b
            grid.addWidget(b, i // 4, i % 4)
        c.add(grid)
        self.desc = label("", "muted")
        self.group.buttonToggled.connect(lambda _b, on: on and self._desktop_chosen())
        c.add(self.desc)
        f = c.form()
        self.edition = combo([(e["id"], e["name"]) for e in dsk.editions()], "full")
        self.edition.currentIndexChanged.connect(lambda _i: self._describe())
        f.addRow("Edition:", self.edition)
        self.edition_desc = label("", "muted")
        f.addRow("", self.edition_desc)
        self.remove_others = QCheckBox("Remove other Debian desktop tasks (task-*-desktop)")
        f.addRow("", self.remove_others)

        # Eduka-Desktop is one of the desktops: its source and defaults show when it is chosen.
        self.eduka_card = c = self.card("Eduka-Desktop", "Eduka-Panel, Eduka-Menu and Eduka-Menu-Settings are "
                                                         "built from git into a .deb when Eduka-Desktop is set up.")
        f = c.form()
        self.repo = QLineEdit(settings().get("eduka_desktop", "repo"))
        f.addRow("Git repository or folder:", hbox(self.repo, button("Folder...", self.choose_folder)))
        self.ref = QLineEdit(settings().get("eduka_desktop", "ref"))
        self.ref.setPlaceholderText("default branch")
        f.addRow("Branch / tag:", self.ref)
        self.ed_state = label("", "muted")
        f.addRow("Status:", self.ed_state)
        c.add(hbox(button("Build .deb only", self.build_deb), button("Install a .deb...", self.install_deb), None))
        c.add(label("Defaults for new users (copied to the live user and every user created after "
                    "installation; /etc/skel/.config/eduka-desktop):", "muted"))
        self.tabs = QTabWidget()
        c.add(self.tabs)
        self.forms = {}

        c = self.card("2. Login screen, session type and compositor",
                      "Set to what fits the chosen desktop (marked 'recommended'). Change anything you like.")
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
        self.dm_group.buttonToggled.connect(lambda _b, on: on and self._dm_changed())
        f = c.form()
        self.sddm_theme = combo([(t, t) for t, _p in dsk.catalog()["sddm_themes"]])
        self.sddm_row = hbox(self.sddm_theme, None)
        f.addRow("SDDM theme:", self.sddm_row)
        self.st_type = combo([])
        self.st_type.currentIndexChanged.connect(self._compositors)
        f.addRow("Session type:", self.st_type)
        self.comp = combo([])
        self.comp.currentIndexChanged.connect(self._comp_desc)
        f.addRow("Compositor:", self.comp)
        self.preset = combo([("shadows", "Shadows and fading"), ("light", "Light (fading only)"),
                             ("glass", "Glass (blur, needs OpenGL)"), ("off", "Effects off")])
        f.addRow("Effects (picom):", self.preset)
        self.comp_desc = label("", "muted")
        f.addRow("", self.comp_desc)
        self.wm = combo(dsk.catalog()["window_managers_for_lxqt"])
        self.wm_label = label("Window manager of LXQt:")
        f.addRow(self.wm_label, self.wm)
        self.recommend_note = label("", "muted")
        c.add(self.recommend_note)
        c.add(hbox(button("Check which login screens this release has", self.check_dms), None,
                   button("Use the recommendations", self._desktop_chosen)))
        self.current = label("", "muted")
        c.add(self.current)

        self.apply_btn = button("Add to Review & Apply", self.add_change, "primary")
        self.apply_btn.setMinimumHeight(40)
        self.add(hbox(label("One change for everything above: the desktop, its login screen, session type and "
                            "compositor.", "muted"), None, self.apply_btn))
        self.eduka_card.setVisible(False)
        self._describe()

    def _edition_names(self):
        """Edition names in the selected desktop's own words."""
        de_id = self._selected()
        current = self.edition.currentData() or "full"
        self.edition.blockSignals(True)
        self.edition.clear()
        for e in dsk.editions():
            name = dsk.edition_name(de_id, e["id"])[0] if de_id else e["name"]
            self.edition.addItem("{} — {}".format(e["name"], name) if de_id else name, e["id"])
        self.edition.setCurrentIndex(max(0, self.edition.findData(current)))
        self.edition.blockSignals(False)

    def _debian_text(self, packages):
        """Description of the edition's main package from the image's APT lists (cached)."""
        if not self.project or not packages:
            return ""
        cache = getattr(self, "_desc_cache", {})
        missing = [p for p in packages[:1] if p not in cache]
        if missing:
            cache.update(dsk.package_descriptions(self.project.rootfs, missing))
            for p in missing:
                cache.setdefault(p, "")
            self._desc_cache = cache
        return cache.get(packages[0], "")

    def _describe(self):
        ed = self.edition.currentData()
        de_id = self._selected()
        if not de_id:
            self.edition_desc.setText({e["id"]: e["description"] for e in dsk.editions()}.get(ed, ""))
            self.desc.setText("Choose a desktop or window manager.")
            return
        name, summary = dsk.edition_name(de_id, ed)
        self.edition_desc.setText("<b>{}</b>: {}".format(name, summary))
        d = dsk.desktop(de_id)
        pkgs, apps, norec = dsk.edition_plan(de_id, ed)
        text = "<b>{}</b>: {}<br>Packages: {}{}".format(d["name"], d["description"], " ".join(pkgs),
                                                     " (without recommended packages)" if norec else "")
        debian = self._debian_text(pkgs)
        if debian:
            text += "<br>Debian: <i>{} — {}</i>".format(pkgs[0], debian)
        if apps:
            text += "<br>Applications: " + " ".join(apps)
        if d.get("note"):
            text += "<br><i>{}</i>".format(d["note"])
        self.desc.setText(text)

    def _selected(self):
        for de_id, b in self.tiles.items():
            if b.isChecked():
                return de_id
        return None

    def refresh(self):
        if not self.project:
            return
        rootfs = self.project.rootfs
        installed = set(dsk.installed_desktops(rootfs))
        for de_id, b in self.tiles.items():
            d = dsk.desktop(de_id)
            b.setText("{}{}\n{}".format(d["name"], "  ✓" if de_id in installed else "",
                                         "Window manager" if d["kind"] == "wm" else "Desktop"))
        st = self.project.state.get("desktop", {})
        chosen = st.get("id") if st.get("id") in self.tiles else next(iter(installed & set(self.tiles)), None)
        if chosen and not self._selected():
            self.tiles[chosen].setChecked(True)  # fills in the recommendations
            if st.get("edition"):
                self.edition.setCurrentIndex(max(0, self.edition.findData(st["edition"])))
            self._restore(st)
        dm = dsk.detect_display_manager(rootfs)
        self.current.setText("In the image now: login screen {} · default session {} · session type {}".format(
            dm or "none", st.get("session") or "not set", st.get("session_type") or "not set"))
        apply_now = self.main.collect_changes() is False
        self.apply_btn.setText("Apply now" if apply_now else "Add to Review & Apply")
        if self._selected() == "eduka":
            self._eduka_state()

    def _restore(self, st):
        """Show what was applied before instead of the recommendations."""
        if st.get("session_type") and self.st_type.findData(st["session_type"]) >= 0:
            self.st_type.setCurrentIndex(self.st_type.findData(st["session_type"]))
        comp = st.get("compositor", {})
        if comp.get("id") and self.comp.findData(comp["id"]) >= 0:
            self.comp.setCurrentIndex(self.comp.findData(comp["id"]))
            self.preset.setCurrentIndex(max(0, self.preset.findData(comp.get("preset"))))
        if st.get("dm") in self.dm_tiles:
            self.dm_tiles[st["dm"]].setChecked(True)

    def _eduka_state(self):
        ed = EdukaDesktop(self.project)
        iv = ed.installed_version()
        sv = ed.source_version() if ed.src.exists() else ""
        info = self.project.state.get("eduka_desktop", {})
        self.ed_state.setText("Installed: {}   ·   Source: {} {}".format(
            iv or "not installed", sv or "not fetched",
            ("(" + info.get("commit", "") + ")") if info.get("commit") else ""))
        self._build_forms(ed)

    # The choice follows the desktop ------------------------------------------------------
    def _desktop_chosen(self):
        de = self._selected()
        self._edition_names()
        self._describe()
        if not de:
            return
        d = dsk.desktop(de)
        rec = dsk.recommend(de, self.project)
        self._rec = rec
        for dm_id, b in self.dm_tiles.items():
            name = next(x["name"] for x in dsk.catalog()["display_managers"] if x["id"] == dm_id)
            desc = next(x["description"] for x in dsk.catalog()["display_managers"] if x["id"] == dm_id)
            b.setText("{}{}\n{}".format(name, "  (recommended)" if dm_id == rec["dm"] else "", desc))
        if rec["dm"] in self.dm_tiles:
            self.dm_tiles[rec["dm"]].setChecked(True)
        self.st_type.blockSignals(True)
        self.st_type.clear()
        for kind, text in (("x11", "X11 (Xorg)"), ("wayland", "Wayland")):
            if kind in d.get("sessions", {}):
                self.st_type.addItem(text + ("  (recommended)" if kind == rec["session_type"] else ""), kind)
        self.st_type.setCurrentIndex(max(0, self.st_type.findData(rec["session_type"])))
        self.st_type.blockSignals(False)
        self._compositors()
        lxqt = de in ("lxqt", "eduka")
        self.wm.setVisible(lxqt)
        self.wm_label.setVisible(lxqt)
        self.eduka_card.setVisible(de == "eduka")
        if de == "eduka" and self.project:
            self._eduka_state()
        self.recommend_note.setText("Recommended for {}: login screen {}, {} session, compositor {}.{}".format(
            d["name"], rec["dm"], "Wayland" if rec["session_type"] == "wayland" else "X11", rec["compositor"],
            " (" + "; ".join(rec["why"]) + ")" if rec["why"] else ""))
        self._dm_changed()

    def _dm_changed(self):
        self.sddm_row.setEnabled(self._dm_selected() == "sddm")

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
    def add_change(self):
        de = self._selected()
        if not de:
            QMessageBox.information(self, "Desktop", "Choose a desktop or window manager first.")
            return
        d = dsk.desktop(de)
        ed = self.edition.currentData()
        proj = self.project
        st = proj.state.get("desktop", {})
        installed = de in set(dsk.installed_desktops(proj.rootfs))
        install = not installed or st.get("id") != de or st.get("edition") != ed
        dm, kind = self._dm_selected(), self.st_type.currentData()
        comp, preset = self.comp.currentData(), self.preset.currentData()
        theme = self.sddm_theme.currentData() if dm == "sddm" else None
        wm = self.wm.currentData() if de in ("lxqt", "eduka") else None
        rem = self.remove_others.isChecked()
        src = (self.repo.text().strip() or None, self.ref.text().strip()) if de == "eduka" else None
        defaults = None
        if de == "eduka" and self.forms:
            defaults = {section: {k: widget_value(w, orig) for k, (w, orig) in editors.items()}
                        for section, editors in self.forms.items()}
        what = "{} ({})".format(d["name"], self.edition.currentText().split(" — ")[0]) if install else d["name"]

        def work(t):
            m = dsk.DesktopManager(proj)
            if install:
                t.set_stage("Installing " + d["name"])
                m.install(de, dm_id=dm, remove_others=rem, edition=ed, eduka_src=src)
            elif dm:
                m.set_display_manager(dm)
            if kind:
                m.set_session_type(de, kind)
            if comp:
                m.set_compositor(comp, preset)
            if theme:
                m.set_sddm_theme(theme)
            if wm:
                m.set_lxqt_window_manager(wm)
            if defaults:
                EdukaDesktop(proj).write_defaults(defaults.get("panel"), defaults.get("menu"), defaults.get("desktop"))
            proj.state.setdefault("desktop", {})["dm"] = dm
            proj.save()
        self.task("Set up desktop: {}, login {}, {} session, compositor {}".format(
            what, dm or "unchanged", "Wayland" if kind == "wayland" else "X11", comp or "none"), work)

    def _dm_selected(self):
        for dm_id, b in self.dm_tiles.items():
            if b.isChecked():
                return dm_id
        return None

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

    def _compositors(self):
        kind = self.st_type.currentData() or "x11"
        self.comp.clear()
        de = self._selected()
        if not de:
            return
        choices, best = dsk.compositors_for(de, kind)
        for c in choices:
            self.comp.addItem(c["name"] + ("  (recommended)" if c["id"] == best else ""), c["id"])
        if self.comp.findData(best) >= 0:
            self.comp.setCurrentIndex(self.comp.findData(best))
        self._comp_desc()

    def _comp_desc(self):
        cid = self.comp.currentData()
        native = any(c["id"] == cid and c["kind"] == "native" for c in dsk.catalog()["compositors"])
        self.preset.setEnabled(cid == "picom")
        if native:
            self.comp_desc.setText("")
        for c in dsk.catalog()["compositors"]:
            if c["id"] == cid:
                self.comp_desc.setText(c["description"])

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

    def install_deb(self):
        path, _ = QFileDialog.getOpenFileName(self, "Eduka-Desktop package", "", "Debian packages (*.deb)")
        if path:
            proj = self.project
            self.task("Install Eduka-Desktop .deb", lambda t: EdukaDesktop(proj).install(path))
