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
from eduka_customizer.core.flathub import CATEGORIES, FEATURED
from eduka_customizer.gui.pages.appearance import IMAGES, ColorButton
from eduka_customizer.gui.widgets import Card, DropZone, FilePicker, ImagePreview, Page, button, combo, hbox, label

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
                               ("iso", "Debian or Debian-based live ISO"),
                               ("bootstrap", "New Debian base (build from scratch)")])
        f.addRow("Source:", self.src_kind)
        self.iso = FilePicker("ISO image", "ISO images (*.iso)")
        f.addRow("ISO file:", self.iso)
        self.bs_arch = combo(["amd64", "i386", "arm64"])
        f.addRow("Architecture (new base):", self.bs_arch)
        self.src_note = label("", "muted")
        c.add(self.src_note)
        c.add(label("Recommended source: the Debian live <b>standard</b> ISO (no desktop, minimal). Any Debian "
                    "live ISO or a Debian derivative such as LMDE works too.", "muted"))
        c = self._card(lay, "What is your distribution for?",
                       "Fills the next steps with recommendations (desktop, login screen, look, applications). "
                       "Change anything you like afterwards, or choose 'Other' to decide everything yourself.")
        from eduka_customizer.core import profiles
        self.w_purpose = combo([(p["id"], "{} — {}".format(p["name"], p["description"]))
                                for p in profiles.catalog()], "other")
        self.w_purpose.currentIndexChanged.connect(lambda _i: self._apply_purpose())
        c.add(self.w_purpose)
        self.w_isoed = combo([(e["id"], "{} — {}".format(e["name"], e["description"]))
                              for e in profiles.iso_editions()], "full_apps")
        self.w_isoed.currentIndexChanged.connect(lambda _i: self._apply_purpose())
        c.add(label("ISO edition", "cardTitle"))
        c.add(self.w_isoed)

    def _identity(self, lay):
        c = self._card(lay, "Name your distribution")
        f = c.form()
        self.w_name = QLineEdit()
        self.w_name.setPlaceholderText("e.g. My Linux")
        self.w_id = QLineEdit()
        self.w_id.setPlaceholderText("e.g. mylinux")
        self.w_version = QLineEdit("1.0")
        self.w_codename = QLineEdit("Kameli")
        self.w_home = QLineEdit()
        self.w_home.setPlaceholderText("https://...")
        self.w_host = QLineEdit()
        self.w_host.setPlaceholderText("e.g. mylinux")
        self.w_user = QLineEdit("live")
        for text, w in (("Name:", self.w_name), ("ID:", self.w_id), ("Version:", self.w_version),
                        ("Codename:", self.w_codename), ("Home page:", self.w_home),
                        ("Host name:", self.w_host), ("Live user:", self.w_user)):
            f.addRow(text, w)
        from eduka_customizer.core.users import PASSWORD_MODES
        self.w_pwmode = combo(list(PASSWORD_MODES.items()), "none")
        self.w_pw = QLineEdit()
        self.w_pw2 = QLineEdit()
        for e, hint in ((self.w_pw, "password"), (self.w_pw2, "repeat the password")):
            e.setEchoMode(QLineEdit.EchoMode.Password)
            e.setPlaceholderText(hint)
        self.w_pwmode.currentIndexChanged.connect(
            lambda _i: [e.setEnabled(self.w_pwmode.currentData() == "custom") for e in (self.w_pw, self.w_pw2)])
        self.w_pw.setEnabled(False)
        self.w_pw2.setEnabled(False)
        f.addRow("Live password:", hbox(self.w_pwmode, self.w_pw, self.w_pw2))
        self._pw_hash = (None, None)
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
        from eduka_customizer.gui.pages.language import language_combo
        self.w_locale = language_combo("en_US.UTF-8")
        self.w_extra = QLineEdit("pt_PT.UTF-8 id_ID.UTF-8")
        self.w_tz = combo(["Asia/Dili", "Asia/Jakarta", "Europe/Lisbon", "UTC", "America/Sao_Paulo"],
                          "Asia/Dili", editable=True)
        self.w_kb = QLineEdit("us")
        f.addRow("Language:", self.w_locale)
        f.addRow("Extra languages:", self.w_extra)
        f.addRow("Time zone:", self.w_tz)
        f.addRow("Keyboard:", self.w_kb)
        self.w_packs = QCheckBox("Install translations and spell checking")
        self.w_packs.setChecked(True)
        self.w_langmenu = QCheckBox("Language choice in the ISO boot menu")
        self.w_langmenu.setChecked(True)
        f.addRow("", self.w_packs)
        f.addRow("", self.w_langmenu)

    def _desktop(self, lay):
        c = self._card(lay, "Desktop, session and login screen")
        f = c.form()
        self.w_de = combo([("", "No desktop — keep what the ISO has (or a server)")] +
                          [(d["id"], "{} — {}".format(d["name"], d["description"]))
                           for d in dsk.catalog()["desktops"]], "")
        self.w_de.currentIndexChanged.connect(self._de_changed)
        f.addRow("Desktop:", self.w_de)
        self.w_deed = combo([(e["id"], "{} — {}".format(e["name"], e["description"])) for e in dsk.editions()],
                            "full")
        f.addRow("Edition:", self.w_deed)
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
        self.w_assets = []
        drop = DropZone("Drop your own themes, icons, cursors, fonts or more wallpapers here "
                        "(folders, archives or files)")
        drop.dropped.connect(self._add_assets)
        c.add(drop)
        self.w_assets_note = label("", "muted")
        c.add(self.w_assets_note)

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
        c.add(hbox(button("Choose from all Debian packages (search)...", self._browse_packages),
                   button("Remove applications of the ISO...", self._remove_apps), None))
        self.w_remove_apps = []
        self.w_apps_note = label("", "muted")
        c.add(self.w_apps_note)
        c = self._card(lay, "Flatpak apps from Flathub")
        self.w_flat = QListWidget()
        self.w_flat.setMinimumHeight(160)
        titles = dict(CATEGORIES)
        for app_id, name, summary, cat in FEATURED:
            it = QListWidgetItem("{} — {}  ({})".format(name, summary, titles.get(cat, cat)))
            it.setData(Qt.ItemDataRole.UserRole, app_id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
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
        self.w_email.setPlaceholderText("archive e-mail, e.g. archive@example.org")
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
    def _apply_purpose(self):
        """Pre-fill desktop, login screen, look and applications from the chosen purpose."""
        from eduka_customizer.core import profiles
        p = profiles.get(self.w_purpose.currentData())
        ed = profiles.iso_edition(self.w_isoed.currentData())
        self.w_deed.setCurrentIndex(max(0, self.w_deed.findData(ed["desktop_edition"])))
        if p["id"] == "other":
            return
        self.w_de.setCurrentIndex(max(0, self.w_de.findData(p.get("desktop") or "")))
        self._de_changed()
        if p.get("dm") and self.w_dm.findData(p["dm"]) >= 0:
            self.w_dm.setCurrentIndex(self.w_dm.findData(p["dm"]))
        if p.get("session_type") and self.w_type.findData(p["session_type"]) >= 0:
            self.w_type.setCurrentIndex(self.w_type.findData(p["session_type"]))
        self._type_changed()
        if p.get("picom_preset") and self.w_preset.findData(p["picom_preset"]) >= 0:
            self.w_preset.setCurrentIndex(self.w_preset.findData(p["picom_preset"]))
        for combo_, key in ((self.w_icons, "icons"), (self.w_gtk, "gtk")):
            pkg = (p.get(key) or ["", ""])[0]
            combo_.setCurrentIndex(max(0, combo_.findData(pkg)))
        self.w_darkmode.setChecked(bool(p.get("dark")))
        for cb, _pkgs in self.w_groups:
            cb.setChecked(False)
        minimal = ed["id"] == "minimal"
        self.w_more.setText(" ".join(p.get("minimal_packages", []) if minimal else p.get("packages", [])))
        flats = p.get("flatpaks", []) if ed["id"] == "full_apps" else []
        for i in range(self.w_flat.count()):
            it = self.w_flat.item(i)
            it.setCheckState(Qt.CheckState.Checked if it.data(Qt.ItemDataRole.UserRole) in flats
                             else Qt.CheckState.Unchecked)
        self.w_ply.setCurrentIndex(max(0, self.w_ply.findData("generate" if p.get("plymouth") and not minimal
                                                              else "keep")))

    def _need_system(self):
        if self.project and self.project.has_rootfs():
            return True
        QMessageBox.information(self, "Quick Wizard", "This needs the system of an open project (extract the ISO "
                                "first). Until then, type package names in the field above.")
        return False

    def _browse_packages(self):
        if not self._need_system():
            return
        from eduka_customizer.qt.widgets import QDialog, QDialogButtonBox
        from eduka_customizer.gui.package_browser import PackageBrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("All Debian packages")
        dlg.resize(1100, 700)
        v = QVBoxLayout(dlg)
        browser = PackageBrowser()
        v.addWidget(browser)
        browser.load(self.project.rootfs)
        browser.select(self.w_more.text().split())
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        v.addWidget(box)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            install, remove = browser.changes()
            self.w_more.setText(" ".join(install))
            self.w_remove_apps = sorted(set(self.w_remove_apps) | set(remove))
            self._apps_note()

    def _remove_apps(self):
        if not self._need_system():
            return
        from eduka_customizer.qt.widgets import QDialog, QDialogButtonBox
        from eduka_customizer.gui.package_browser import AppRemover
        dlg = QDialog(self)
        dlg.setWindowTitle("Remove applications of the ISO")
        dlg.resize(700, 560)
        v = QVBoxLayout(dlg)
        remover = AppRemover()
        v.addWidget(remover)
        remover.load(self.project.rootfs)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        v.addWidget(box)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.w_remove_apps = sorted(set(self.w_remove_apps) | set(remover.selected()))
            self._apps_note()

    def _apps_note(self):
        self.w_apps_note.setText("Removed from the ISO: " + " ".join(self.w_remove_apps) if self.w_remove_apps else "")

    def _add_assets(self, paths):
        self.w_assets += [p for p in paths if p not in self.w_assets]
        self.w_assets_note.setText("Will be added: " + ", ".join(os.path.basename(p) for p in self.w_assets))

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
        # Only compositors that suit the desktop: its own (Mutter, Muffin, KWin, xfwm4, Marco,
        # Budgie) instead of picom where the desktop composites itself, to avoid conflicts.
        choices, default = dsk.compositors_for(self.w_de.currentData(), kind)
        for comp in choices:
            self.w_comp.addItem(comp["name"] + ("  (recommended)" if comp["id"] == default else ""), comp["id"])
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
                return "The ID must be lower case letters, digits and '-' (e.g. mylinux)."
            if not self.w_name.text().strip():
                return "Enter a name."
            from eduka_customizer.core.users import check_username
            try:
                check_username(self.w_user.text().strip())
            except ValueError as e:
                return str(e)
            if self.w_pwmode.currentData() == "custom":
                if not self.w_pw.text():
                    return "Type the live password twice, or choose another password option."
                if self.w_pw.text() != self.w_pw2.text():
                    return "The two passwords are not the same."
        return ""

    def _live_user(self):
        """Live user for the recipe; a password is stored only as its hash."""
        mode = self.w_pwmode.currentData()
        live = {"username": self.w_user.text().strip() or "user",
                "fullname": "Live", "password_mode": mode}
        if mode == "custom" and self.w_pw.text():
            from eduka_customizer.core.users import sha512_crypt
            if self._pw_hash[0] != self.w_pw.text():
                self._pw_hash = (self.w_pw.text(), sha512_crypt(self.w_pw.text()))
            live["password_hash"] = self._pw_hash[1]
        return live

    def recipe(self):
        name, os_id = self.w_name.text().strip(), self.w_id.text().strip()
        steps = [{"action": "sources", "suite": self.w_suite.currentData(),
                  "backports": self.w_backports.isChecked() and self.w_suite.currentData() == "stable"}]
        if self.w_upgrade.isChecked():
            steps.append({"action": "apt-upgrade"})
        steps.append({"action": "identity", "name": name, "id": os_id, "version": self.w_version.text().strip(),
                      "codename": self.w_codename.text().strip(), "home_url": self.w_home.text().strip(),
                      "hostname": self.w_host.text().strip() or os_id, "live_user": self.w_user.text().strip() or "live",
                      "live_fullname": "Live",
                      "volume_label": (name.upper().replace(" ", "_") + "_" + self.w_version.text().strip())[:32]})
        steps.append({"action": "users", "live": self._live_user()})
        de = self.w_de.currentData()
        if self.w_remove_apps:
            steps.append({"action": "apt-remove", "packages": list(self.w_remove_apps)})
        if de:
            steps.append({"action": "desktop", "id": de, "dm": self.w_dm.currentData(),
                          "remove_others": self.w_remove.isChecked(), "edition": self.w_deed.currentData()})
            if self.w_type.currentData():
                steps.append({"action": "session-type", "desktop": de, "type": self.w_type.currentData()})
            if self.w_comp.currentData():
                steps.append({"action": "compositor", "id": self.w_comp.currentData(),
                              "preset": self.w_preset.currentData()})
        pkgs = [p for cb, ps in self.w_groups if cb.isChecked() for p in ps] + self.w_more.text().split()
        pkgs = [p for i, p in enumerate(pkgs) if p not in pkgs[:i]]
        if pkgs:
            steps.append({"action": "apt-install", "packages": pkgs})
        apps = [self.w_flat.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.w_flat.count())
                if self.w_flat.item(i).checkState() == Qt.CheckState.Checked]
        if apps:
            steps.append({"action": "flatpak", "apps": apps, "firstboot": self.w_flat_mode.currentData() == "firstboot"})
        from eduka_customizer.gui.pages.language import combo_locale
        default = combo_locale(self.w_locale)
        extra = [l for l in self.w_extra.text().split() if l != default]
        # After the applications, so their translations are installed too.
        steps.append({"action": "language", "default": default, "extra": extra,
                      "timezone": self.w_tz.currentText().strip(), "keyboard": self.w_kb.text().strip() or "us",
                      "packs": self.w_packs.isChecked(),
                      "boot_menu": [default] + extra if self.w_langmenu.isChecked() and extra else []})
        icon = dict((p, t) for p, _n, t in ICON_PACKS).get(self.w_icons.currentData(), "")
        gtk = dict((p, t) for p, _n, t in GTK_PACKS).get(self.w_gtk.currentData(), "")
        packs = [p for p in (self.w_icons.currentData(), self.w_gtk.currentData()) if p]
        if packs or self.w_darkmode.isChecked():
            steps.append({"action": "themes", "packs": packs, "icons": icon, "gtk": gtk,
                          "dark": self.w_darkmode.isChecked()})
        if self.w_assets:
            steps.append({"action": "assets", "files": list(self.w_assets)})
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
            # The wizard did every step: all menus are open for fine-tuning.
            proj.mark_all_steps()
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

