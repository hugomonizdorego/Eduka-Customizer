"""Quick Wizard: build a complete distribution with Next, Next, Finish.

Every answer becomes a step of a recipe (see core/recipe.py); Finish runs
the recipe and, if wanted, builds the ISO. The recipe is saved in the
project so the same build can be repeated or edited later.
"""

import json
import os
from pathlib import Path

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QGridLayout, QLineEdit, QListWidget,
                                          QListWidgetItem, QMessageBox, QPlainTextEdit,
                                          QStackedWidget, QWidget, QVBoxLayout)

from eduka_customizer.core import desktop as dsk
from eduka_customizer.core.config import settings
from eduka_customizer.core.flatpak import EDUCATION_PICKS
from eduka_customizer.gui.pages.appearance import IMAGES, ColorButton
from eduka_customizer.gui.widgets import Card, FilePicker, ImagePreview, Page, button, combo, hbox, label

STEPS = ["Source", "Identity", "Base system", "Desktop", "Look", "Applications", "Branding", "Finish"]

ICON_PACKS = [("", "Keep current", ""), ("papirus-icon-theme", "Papirus", "Papirus"),
              ("numix-icon-theme-circle", "Numix Circle", "Numix-Circle"),
              ("elementary-xfce-icon-theme", "elementary Xfce", "elementary-xfce"),
              ("breeze-icon-theme", "Breeze", "breeze"), ("adwaita-icon-theme", "Adwaita", "Adwaita"),
              ("yaru-theme-icon", "Yaru", "Yaru")]
GTK_PACKS = [("", "Keep current", ""), ("arc-theme", "Arc", "Arc"), ("materia-gtk-theme", "Materia", "Materia"),
             ("numix-gtk-theme", "Numix", "Numix"), ("greybird-gtk-theme", "Greybird", "Greybird"),
             ("breeze-gtk-theme", "Breeze", "Breeze"), ("yaru-theme-gtk", "Yaru", "Yaru"),
             ("orchis-gtk-theme", "Orchis", "Orchis")]
APP_GROUPS = [
    ("Office", ["libreoffice", "libreoffice-gtk3", "hunspell-en-us"], True),
    ("Internet", ["firefox-esr", "thunderbird"], True),
    ("Media", ["vlc", "audacious"], True),
    ("Graphics", ["gimp", "inkscape", "shotwell"], False),
    ("Education", ["gcompris-qt", "kgeography", "kalzium", "stellarium", "tuxpaint"], True),
    ("Accessibility", ["orca", "speech-dispatcher-espeak-ng", "onboard"], True),
    ("Programming", ["git", "build-essential", "python3-pip", "geany"], False),
    ("System tools", ["gparted", "synaptic", "gnome-disk-utility", "htop"], True),
    ("Installer (Calamares)", ["calamares-settings-debian"], True),
]


class WizardPage(Page):
    title = "Quick Wizard"
    nav_title = "Quick Wizard ✨"
    subtitle = ("Answer a few questions and Eduka-Customizer builds your distribution: source, "
                "identity, desktop, look, applications and branding — then Finish.")
    icon_names = ("tools-wizard", "system-run", "applications-system")
    needs_rootfs = False

    def build(self):
        self.steps_bar = label("", wrap=False)
        self.back = button("◀  Back", self.go_back)
        self.next = button("Next  ▶", self.go_next, "primary")
        self.add(hbox(self.back, self.steps_bar, None, self.next))
        self.stack = QStackedWidget()
        self.add(self.stack)
        for builder in (self._source, self._identity, self._base, self._desktop, self._look,
                        self._apps, self._branding, self._finish):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            builder(lay)
            lay.addStretch(1)
            self.stack.addWidget(w)
        self._update()

    # Steps -------------------------------------------------------------------
    def _card(self, lay, title, subtitle=""):
        c = Card(title, subtitle)
        lay.addWidget(c)
        return c

    def _source(self, lay):
        c = self._card(lay, "Where does the system come from?")
        f = c.form()
        self.folder = FilePicker("Project folder", directory=True)
        self.folder.setText(os.path.join(settings().get("general", "projects_dir"), "my-distro"))
        f.addRow("Project folder:", self.folder)
        self.src_kind = combo([("current", "Keep the system of the open project"),
                               ("iso", "Debian or Edukasaun OS live ISO"),
                               ("bootstrap", "New Debian base (build from scratch)")])
        f.addRow("Source:", self.src_kind)
        self.iso = FilePicker("ISO image", "ISO images (*.iso)")
        f.addRow("ISO file:", self.iso)
        self.bs_arch = combo(["amd64", "i386", "arm64"])
        f.addRow("Architecture (new base):", self.bs_arch)
        self.src_note = label("", "muted")
        c.add(self.src_note)

    def _identity(self, lay):
        c = self._card(lay, "Name your distribution")
        f = c.form()
        self.w_name = QLineEdit("Edukasaun OS")
        self.w_id = QLineEdit("edukasaun")
        self.w_version = QLineEdit("1.0")
        self.w_codename = QLineEdit("Kameli")
        self.w_home = QLineEdit("https://edukasaun.org")
        self.w_host = QLineEdit("edukasaun")
        self.w_user = QLineEdit("eduka")
        for text, w in (("Name:", self.w_name), ("ID:", self.w_id), ("Version:", self.w_version),
                        ("Codename:", self.w_codename), ("Home page:", self.w_home),
                        ("Host name:", self.w_host), ("Live user:", self.w_user)):
            f.addRow(text, w)
        self.w_logo = FilePicker("Logo", "Images (*.png *.svg)")
        self.w_logo_prev = ImagePreview(80, 80)
        self.w_logo.changed.connect(lambda p: self.w_logo_prev.show_file(p))
        f.addRow("Logo:", hbox(self.w_logo, self.w_logo_prev))
        self.w_accent = ColorButton("#00a879")
        self.w_dark = ColorButton("#0f2f27")
        f.addRow("Colors:", hbox(label("Accent"), self.w_accent, label("Dark"), self.w_dark, None))

    def _base(self, lay):
        c = self._card(lay, "Debian base and language")
        f = c.form()
        self.w_suite = combo([("stable", "Debian stable (recommended)"), ("testing", "Debian testing"),
                              ("sid", "Debian sid (unstable)")])
        f.addRow("Follow:", self.w_suite)
        self.w_backports = QCheckBox("Enable backports (newer kernels and drivers for stable)")
        f.addRow("", self.w_backports)
        self.w_upgrade = QCheckBox("Upgrade all packages first")
        self.w_upgrade.setChecked(True)
        f.addRow("", self.w_upgrade)
        self.w_locale = combo(["en_US.UTF-8", "pt_PT.UTF-8", "pt_BR.UTF-8", "id_ID.UTF-8", "fr_FR.UTF-8",
                               "es_ES.UTF-8", "de_DE.UTF-8"], "en_US.UTF-8", editable=True)
        self.w_extra = QLineEdit("pt_PT.UTF-8 id_ID.UTF-8")
        self.w_tz = combo(["Asia/Dili", "Asia/Jakarta", "Europe/Lisbon", "UTC", "America/Sao_Paulo"],
                          "Asia/Dili", editable=True)
        self.w_kb = QLineEdit("us")
        f.addRow("Language:", self.w_locale)
        f.addRow("Extra languages:", self.w_extra)
        f.addRow("Time zone:", self.w_tz)
        f.addRow("Keyboard:", self.w_kb)

    def _desktop(self, lay):
        c = self._card(lay, "Desktop, session and login screen")
        f = c.form()
        self.w_de = combo([(d["id"], "{} — {}".format(d["name"], d["description"]))
                           for d in dsk.catalog()["desktops"]])
        self.w_de.currentIndexChanged.connect(self._de_changed)
        f.addRow("Desktop:", self.w_de)
        self.w_type = combo([])
        f.addRow("Session:", self.w_type)
        self.w_comp = combo([])
        self.w_type.currentIndexChanged.connect(self._type_changed)
        f.addRow("Compositor:", self.w_comp)
        self.w_preset = combo([("shadows", "Shadows and fading"), ("light", "Light"),
                               ("glass", "Glass (blur)"), ("off", "Off")])
        f.addRow("Effects:", self.w_preset)
        self.w_dm = combo([(d["id"], "{} — {}".format(d["name"], d["description"]))
                           for d in dsk.catalog()["display_managers"]])
        f.addRow("Login screen:", self.w_dm)
        self.w_remove = QCheckBox("Remove other Debian desktops")
        f.addRow("", self.w_remove)
        self._de_changed()

    def _look(self, lay):
        c = self._card(lay, "Look and feel")
        f = c.form()
        self.w_wall = FilePicker("Wallpaper", IMAGES)
        self.w_wall_prev = ImagePreview(200, 112)
        self.w_wall.changed.connect(lambda p: self.w_wall_prev.show_file(p))
        f.addRow("Wallpaper:", hbox(self.w_wall, self.w_wall_prev))
        self.w_grub = FilePicker("Boot menu background", IMAGES)
        f.addRow("GRUB / boot menu background:", self.w_grub)
        self.w_grub_both = QCheckBox("Use it for the live ISO menu and the installed system")
        self.w_grub_both.setChecked(True)
        f.addRow("", self.w_grub_both)
        self.w_ply = combo([("generate", "Generate a boot splash from my logo"), ("keep", "Keep current"),
                            ("spinner", "Spinner"), ("bgrt", "BGRT (manufacturer logo)")])
        f.addRow("Boot splash (Plymouth):", self.w_ply)
        self.w_icons = combo([(p, n) for p, n, _t in ICON_PACKS], "papirus-icon-theme")
        self.w_gtk = combo([(p, n) for p, n, _t in GTK_PACKS])
        self.w_darkmode = QCheckBox("Prefer dark style")
        f.addRow("Icons:", self.w_icons)
        f.addRow("GTK theme:", self.w_gtk)
        f.addRow("", self.w_darkmode)

    def _apps(self, lay):
        c = self._card(lay, "Applications", "Debian packages")
        grid = QGridLayout()
        self.w_groups = []
        for i, (name, pkgs, default) in enumerate(APP_GROUPS):
            cb = QCheckBox("{}  ({})".format(name, ", ".join(pkgs)))
            cb.setChecked(default)
            self.w_groups.append((cb, pkgs))
            grid.addWidget(cb, i // 2, i % 2)
        c.add(grid)
        self.w_more = QLineEdit()
        self.w_more.setPlaceholderText("More Debian packages, separated by spaces")
        c.add(self.w_more)
        c = self._card(lay, "Flatpak apps from Flathub")
        self.w_flat = QListWidget()
        self.w_flat.setMinimumHeight(160)
        for app_id, name, summary in EDUCATION_PICKS:
            it = QListWidgetItem("{} — {}".format(name, summary))
            it.setData(Qt.ItemDataRole.UserRole, app_id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if app_id in ("org.kde.gcompris", "org.geogebra.GeoGebra")
                             else Qt.CheckState.Unchecked)
            self.w_flat.addItem(it)
        c.add(self.w_flat)
        self.w_flat_mode = combo([("firstboot", "Install on first boot (smaller ISO)"),
                                  ("now", "Install into the ISO now")])
        c.add(self.w_flat_mode)

    def _branding(self, lay):
        c = self._card(lay, "Full distribution branding",
                       "Replace Debian's identity everywhere: os-release, lsb_release, login text, logos, "
                       "desktop-base artwork, GRUB menu, installer. Uses your logo, colors and wallpaper.")
        self.w_brand = QCheckBox("Build and install the <id>-branding package (recommended)")
        self.w_brand.setChecked(True)
        self.w_keyring = QCheckBox("Create my own APT signing key and <id>-archive-keyring package")
        self.w_email = QLineEdit()
        self.w_email.setPlaceholderText("archive e-mail, e.g. archive@edukasaun.org")
        self.w_grubname = QCheckBox("Show my distribution name in the GRUB menu")
        self.w_grubname.setChecked(True)
        for w in (self.w_brand, self.w_grubname, self.w_keyring, self.w_email):
            c.add(w)

    def _finish(self, lay):
        c = self._card(lay, "Ready", "This recipe will be applied. You can still change everything later "
                                     "on the other pages.")
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(320)
        c.add(self.summary)
        self.w_build = QCheckBox("Build the ISO image at the end")
        self.w_build.setChecked(True)
        c.add(self.w_build)

    # Logic ---------------------------------------------------------------------
    def _de_changed(self):
        de = self.w_de.currentData()
        if not de:
            return
        self.w_type.clear()
        for kind, text in (("x11", "X11 (most compatible)"), ("wayland", "Wayland")):
            if kind in dsk.desktop(de).get("sessions", {}):
                self.w_type.addItem(text, kind)
        rec = dsk.desktop(de).get("dm")
        mapping = {"lightdm": "lightdm", "sddm": "sddm", "gdm3": "gdm3"}
        idx = self.w_dm.findData(mapping.get(rec, "lightdm"))
        if idx >= 0:
            self.w_dm.setCurrentIndex(idx)
        self._type_changed()

    def _type_changed(self):
        kind = self.w_type.currentData() or "x11"
        self.w_comp.clear()
        for comp in dsk.catalog()["compositors"]:
            if comp["kind"] == kind:
                self.w_comp.addItem(comp["name"], comp["id"])
        de = self.w_de.currentData()
        default = {"eduka": "picom", "lxqt": "picom", "openbox": "picom", "i3": "picom",
                   "kde": "builtin", "gnome": "builtin", "xfce": "builtin", "mate": "builtin",
                   "cinnamon": "builtin"}.get(de, "none")
        if kind == "wayland":
            default = "labwc"
        idx = self.w_comp.findData(default)
        if idx >= 0:
            self.w_comp.setCurrentIndex(idx)

    def refresh(self):
        has = bool(self.project and self.project.has_rootfs())
        if has:
            ident = self.project.state.get("identity", {})
            self.src_note.setText("Open project: {} ({})".format(self.project.path, self.project.distro.summary()))
            self.folder.setText(str(self.project.path))
            if ident.get("name"):
                self.w_name.setText(ident["name"])
            suite = self.project.distro.suite
            idx = self.w_suite.findData(suite)
            if idx >= 0:
                self.w_suite.setCurrentIndex(idx)
        else:
            self.src_kind.setCurrentIndex(1)
            self.src_note.setText("No project is open: a new one is created in the folder above.")

    def _update(self):
        i = self.stack.currentIndex()
        parts = []
        for n, s in enumerate(STEPS):
            parts.append("<b style='color:#00a879'>{}. {}</b>".format(n + 1, s) if n == i else
                         "{}. {}".format(n + 1, s))
        self.steps_bar.setText("  ›  ".join(parts))
        self.back.setEnabled(i > 0)
        self.next.setText("Finish ✔" if i == len(STEPS) - 1 else "Next  ▶")

    def go_back(self):
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._update()

    def go_next(self):
        i = self.stack.currentIndex()
        problem = self._check(i)
        if problem:
            QMessageBox.warning(self, "Quick Wizard", problem)
            return
        if i == len(STEPS) - 2:
            self.summary.setPlainText(json.dumps(self.recipe(), indent=2, ensure_ascii=False))
        if i == len(STEPS) - 1:
            self.finish()
            return
        self.stack.setCurrentIndex(i + 1)
        self._update()

    def _check(self, step):
        if step == 0:
            kind = self.src_kind.currentData()
            if kind == "current" and not (self.project and self.project.has_rootfs()):
                return "No project with a system is open: choose an ISO or a new Debian base."
            if kind == "iso" and not Path(self.iso.text()).is_file():
                return "Choose the ISO file."
            if not self.folder.text():
                return "Choose a project folder."
        if step == 1:
            import re
            if not re.match(r"^[a-z0-9][a-z0-9-]{1,30}$", self.w_id.text().strip()):
                return "The ID must be lower case letters, digits and '-' (e.g. edukasaun)."
            if not self.w_name.text().strip():
                return "Enter a name."
        return ""

    def recipe(self):
        name, os_id = self.w_name.text().strip(), self.w_id.text().strip()
        steps = [{"action": "sources", "suite": self.w_suite.currentData(),
                  "backports": self.w_backports.isChecked() and self.w_suite.currentData() == "stable"}]
        if self.w_upgrade.isChecked():
            steps.append({"action": "apt-upgrade"})
        steps.append({"action": "identity", "name": name, "id": os_id, "version": self.w_version.text().strip(),
                      "codename": self.w_codename.text().strip(), "home_url": self.w_home.text().strip(),
                      "hostname": self.w_host.text().strip() or os_id, "live_user": self.w_user.text().strip() or "user",
                      "live_fullname": "{} Live User".format(name),
                      "volume_label": (name.upper().replace(" ", "_") + "_" + self.w_version.text().strip())[:32]})
        steps.append({"action": "locale", "default": self.w_locale.currentText().strip(),
                      "extra": self.w_extra.text().split(), "timezone": self.w_tz.currentText().strip(),
                      "keyboard": self.w_kb.text().strip() or "us"})
        de = self.w_de.currentData()
        steps.append({"action": "desktop", "id": de, "dm": self.w_dm.currentData(),
                      "remove_others": self.w_remove.isChecked()})
        if self.w_type.currentData():
            steps.append({"action": "session-type", "desktop": de, "type": self.w_type.currentData()})
        if self.w_comp.currentData():
            steps.append({"action": "compositor", "id": self.w_comp.currentData(),
                          "preset": self.w_preset.currentData()})
        pkgs = [p for cb, ps in self.w_groups if cb.isChecked() for p in ps] + self.w_more.text().split()
        if pkgs:
            steps.append({"action": "apt-install", "packages": pkgs})
        apps = [self.w_flat.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.w_flat.count())
                if self.w_flat.item(i).checkState() == Qt.CheckState.Checked]
        if apps:
            steps.append({"action": "flatpak", "apps": apps, "firstboot": self.w_flat_mode.currentData() == "firstboot"})
        icon = dict((p, t) for p, _n, t in ICON_PACKS).get(self.w_icons.currentData(), "")
        gtk = dict((p, t) for p, _n, t in GTK_PACKS).get(self.w_gtk.currentData(), "")
        packs = [p for p in (self.w_icons.currentData(), self.w_gtk.currentData()) if p]
        if packs or self.w_darkmode.isChecked():
            steps.append({"action": "themes", "packs": packs, "icons": icon, "gtk": gtk,
                          "dark": self.w_darkmode.isChecked()})
        wall = self.w_wall.text()
        if wall:
            steps.append({"action": "wallpaper", "image": wall})
        logo = self.w_logo.text()
        ply = self.w_ply.currentData()
        if ply == "generate" and logo:
            steps.append({"action": "plymouth", "logo": logo, "name": os_id,
                          "background": self.w_dark.color, "color": self.w_accent.color})
        elif ply not in ("keep", "generate"):
            steps.append({"action": "plymouth", "theme": ply})
        grub = self.w_grub.text() or wall
        boot = {"action": "boot", "title": name, "extra_params": "quiet splash", "timeout": 10}
        if grub and self.w_grub_both.isChecked():
            boot["splash"] = grub
        steps.append(boot)
        if self.w_brand.isChecked():
            steps.append({"action": "branding", "name": name, "os_id": os_id,
                          "version": self.w_version.text().strip(), "codename": self.w_codename.text().strip(),
                          "home_url": self.w_home.text().strip(), "logo": logo, "accent": self.w_accent.color,
                          "dark": self.w_dark.color, "wallpaper": wall,
                          "grub_background": grub if self.w_grub_both.isChecked() else "",
                          "grub_name": self.w_grubname.isChecked(),
                          "keyring": self.w_keyring.isChecked(), "email": self.w_email.text().strip()})
        if self.w_build.isChecked():
            steps.append({"action": "build"})
        return {"name": "{} {} (Quick Wizard)".format(name, self.w_version.text().strip()), "steps": steps}

    def finish(self):
        data = self.recipe()
        kind = self.src_kind.currentData()
        folder = self.folder.text().strip()
        if kind != "current" or not self.project or str(self.project.path) != os.path.realpath(folder):
            if kind == "current":
                kind = "iso"
            if not self.main.open_project(folder, create=not Path(folder, "project.json").exists(),
                                          name=self.w_name.text().strip()):
                return
        proj = self.main.project
        if kind in ("iso", "bootstrap") and proj.has_rootfs():
            if QMessageBox.question(self, "Quick Wizard", "This project already has a system. Replace it?") != \
                    QMessageBox.StandardButton.Yes:
                return
        (proj.path / "recipe-wizard.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        iso_path, suite, arch = self.iso.text(), self.w_suite.currentData(), self.bs_arch.currentData()

        def work(t):
            from eduka_customizer.core import recipe
            if kind == "iso":
                from eduka_customizer.core import iso
                t.set_stage("Extracting the ISO")
                iso.extract(proj, iso_path, t.set_progress)
            elif kind == "bootstrap":
                from eduka_customizer.core import bootstrap
                t.set_stage("Bootstrapping Debian " + suite)
                bootstrap.bootstrap(proj, suite, arch)
            result = None
            for n, step in enumerate(data["steps"], 1):
                t.set_stage("Step {}/{}: {}".format(n, len(data["steps"]), step["action"]))
                if step["action"] == "build":
                    from eduka_customizer.core.isobuild import BuildOptions, build
                    result = build(proj, BuildOptions.from_project(proj), t.set_progress, t.set_stage)
                else:
                    recipe.run_step(proj, step, proj.path)
            return result

        def done(out):
            self.main.update_state()
            msg = "Your distribution is ready."
            if out:
                msg += "\n\nISO: {}".format(out)
            QMessageBox.information(self, "Quick Wizard", msg + "\n\nRecipe saved as recipe-wizard.json.")
            self.stack.setCurrentIndex(0)
            self._update()
        self.task("Quick Wizard", work, done)

