"""Distro Branding Studio page: your own distribution identity."""

from dataclasses import asdict

from eduka_customizer.qt.widgets import (QCheckBox, QFileDialog, QLineEdit, QMessageBox, QSpinBox,
                                          QTabWidget, QWidget, QVBoxLayout)

from eduka_customizer.core.distrobrand import BrandingSpec, DistroBranding
from eduka_customizer.gui.pages.appearance import IMAGES, ColorButton
from eduka_customizer.gui.widgets import (FilePicker, FileTreeEditor, ImagePreview, Page, button,
                                          hbox, label)


class BrandingPage(Page):
    title = "Distro Branding"
    nav_title = "Distro Branding"
    subtitle = ("Make the system your own distribution, not just Debian renamed. DistroForge "
                "builds a <id>-branding package that replaces the identity of base-files, "
                "lsb-release, distro-info-data, desktop-base, the Debian logos, GRUB and the "
                "Calamares installer with dpkg diversions, plus an optional archive keyring. "
                "No repository is needed and Debian updates keep your branding.")
    icon_names = ("preferences-desktop-theme-global", "applications-graphics", "emblem-favorite")
    CHANGES = ('Apply distro branding', 'Build edited branding packages')

    def build(self):
        c = self.card("1. Identity and artwork")
        self.source = label("", "muted")
        c.add(self.source)
        c.add(hbox(button("Load from the ISO", self.load_from_image,
                          tooltip="Name, links, logo, wallpaper, login and GRUB backgrounds and colors of the "
                                  "extracted ISO"), None))
        f = c.form()
        self.name = QLineEdit()
        self.os_id = QLineEdit()
        self.version = QLineEdit()
        self.codename = QLineEdit()
        self.home = QLineEdit()
        self.support = QLineEdit()
        self.bugs = QLineEdit()
        self.maint = QLineEdit()
        for text, w in (("Name:", self.name), ("ID (lower case):", self.os_id), ("Version:", self.version),
                        ("Codename:", self.codename), ("Home page:", self.home),
                        ("Support URL:", self.support), ("Bug report URL:", self.bugs),
                        ("Maintainer:", self.maint)):
            f.addRow(text, w)
        self.logo = FilePicker("Logo (PNG or SVG, square)", "Images (*.png *.svg)")
        self.logo_prev = ImagePreview(96, 96)
        self.logo.changed.connect(lambda p: self.logo_prev.show_file(p))
        f.addRow("Logo:", hbox(self.logo, self.logo_prev))
        self.accent = ColorButton("#00a879")
        self.dark = ColorButton("#0f2f27")
        f.addRow("Colors:", hbox(label("Accent"), self.accent, label("Dark"), self.dark, None))
        self.wall = FilePicker("Wallpaper", IMAGES)
        self.login = FilePicker("Login background", IMAGES)
        self.grub = FilePicker("GRUB background (installed system)", IMAGES)
        f.addRow("Wallpaper:", self.wall)
        f.addRow("Login background:", self.login)
        f.addRow("GRUB background:", self.grub)
        c.add(label("Empty login/GRUB backgrounds use the wallpaper. The live boot menu background "
                    "is set on the Appearance page.", "muted"))

        c = self.card("2. What to replace")
        self.opts = {}
        for key, text in (("replace_logos", "Replace Debian logos (desktop-base, icon themes, Plymouth) with your logo"),
                          ("desktop_theme", "desktop-base theme: wallpaper, login and GRUB artwork"),
                          ("grub", "GRUB menu of the installed system (background, timeout, quiet splash)"),
                          ("grub_name", "Show your name in GRUB entries instead of Debian"),
                          ("secure_boot_safe", "Keep Secure Boot working (EFI/debian copy, Calamares EFI id)"),
                          ("calamares", "Brand the Calamares installer (logo, colors, slideshow)")):
            cb = QCheckBox(text)
            self.opts[key] = cb
            c.add(cb)
        self.timeout = QSpinBox()
        self.timeout.setRange(0, 60)
        self.kopts = QLineEdit()
        c.add(hbox(label("GRUB timeout"), self.timeout, label("Kernel options"), self.kopts))
        self.logos_found = label("", "muted")
        c.add(self.logos_found)

        c = self.card("3. APT archive key (optional)",
                      "Your own GnuPG key and <id>-archive-keyring package, like debian-archive-keyring. "
                      "Use it to sign your own repository later. Keep a backup of the secret key!")
        self.email = QLineEdit()
        self.email.setPlaceholderText("archive@example.org")
        self.key_state = label("", "muted")
        c.add(hbox(label("E-mail"), self.email, button("Create key", self.create_key)))
        c.add(self.key_state)
        c.add(hbox(button("Export public key...", lambda: self.export_key(False)),
                   button("Back up secret key...", lambda: self.export_key(True)), None))
        self.with_keyring = QCheckBox("Install the <id>-archive-keyring package into the image")
        c.add(self.with_keyring)

        c = self.card("4. Build")
        self.state = label("", "muted")
        c.add(self.state)
        c.add(hbox(button("Generate source only", self.generate), None,
                   button("Build and install edited source", self.build_installed),
                   button("Apply branding (generate, build, install)", self.apply, "primary")))

        c = self.card("Edit the packages directly",
                      "The Debian source trees (debian/control, changelog, copyright, rules, install, "
                      "postinst, prerm) and every file. Edit, then 'Build and install edited source'.")
        tabs = QTabWidget()
        self.editors = {}
        for key, title in (("branding", "<id>-branding"), ("keyring", "<id>-archive-keyring")):
            w = QWidget()
            lay = QVBoxLayout(w)
            ed = FileTreeEditor()
            lay.addWidget(ed)
            tabs.addTab(w, title)
            self.editors[key] = ed
        c.add(tabs)

    # ----------------------------------------------------------------------
    def _db(self):
        return DistroBranding(self.project)

    def refresh(self):
        if not self.project:
            return
        db = self._db()
        spec = db.spec()
        for w, v in ((self.name, spec.name), (self.os_id, spec.os_id), (self.version, spec.version),
                     (self.codename, spec.codename), (self.home, spec.home_url),
                     (self.support, spec.support_url), (self.bugs, spec.bug_url), (self.maint, spec.maintainer)):
            w.setText(v)
        self.logo.setText(spec.logo)
        self.accent.set(spec.accent)
        self.dark.set(spec.dark)
        self.wall.setText(spec.wallpaper)
        self.login.setText(spec.login_background)
        self.grub.setText(spec.grub_background)
        for k, cb in self.opts.items():
            cb.setChecked(bool(getattr(spec, k)))
        self.timeout.setValue(int(spec.grub_timeout))
        self.kopts.setText(spec.kernel_options)
        self.logos_found.setText("{} Debian logo files found in the image.".format(len(db.debian_logo_files())))
        fpr = db.key_fingerprint() if (db.gnupg / "pubring.kbx").exists() else ""
        self.key_state.setText("Signing key: {}".format(fpr or "none yet"))
        inst = db.installed()
        self.state.setText("Installed in the image: " + ", ".join(
            "{} {}".format(k, v or "(not installed)") for k, v in inst.items()))
        self.editors["branding"].set_root(db.tree(spec) if db.tree(spec).exists() else None)
        self.editors["keyring"].set_root(db.keyring_tree(spec) if db.keyring_tree(spec).exists() else None)
        if not self.project.state.get("branding", {}).get("spec") and self.project.has_rootfs():
            # Nothing chosen yet: start from the ISO itself.
            self.load_from_image(quiet=True)
            self.source.setText("Loaded from the extracted ISO. Change what you like, then build.")
        else:
            self.source.setText("Your branding. <i>Load from the ISO</i> starts again from the extracted ISO.")

    def load_from_image(self, quiet=False):
        from eduka_customizer.core import imageinfo
        ident = imageinfo.identity(self.project)
        named = self.project.state.get("identity", {}).get("name")
        if not named:
            for w, key in ((self.name, "name"), (self.version, "version"), (self.codename, "codename"),
                           (self.home, "home_url"), (self.support, "support_url"), (self.bugs, "bug_url")):
                if ident.get(key):
                    w.setText(ident[key])
            if ident.get("id"):
                self.os_id.setText(ident["id"])
        art = imageinfo.copy_artwork(self.project)
        for w, key in ((self.logo, "logo"), (self.wall, "wallpaper"), (self.login, "login_background"),
                       (self.grub, "grub_background")):
            if art.get(key):
                w.setText(art[key])
        if art.get("accent"):
            self.accent.set(art["accent"])
        if art.get("dark"):
            self.dark.set(art["dark"])
        if not quiet:
            self.main.stage_label.setText("Loaded from the ISO: " + ", ".join(sorted(art)) if art else
                                          "The ISO has no artwork DistroForge recognizes")

    def spec(self):
        s = BrandingSpec.from_project(self.project)
        s.name, s.os_id, s.version = self.name.text().strip(), self.os_id.text().strip(), self.version.text().strip()
        s.codename, s.home_url = self.codename.text().strip(), self.home.text().strip()
        s.support_url, s.bug_url, s.maintainer = self.support.text().strip(), self.bugs.text().strip(), self.maint.text().strip()
        s.logo, s.wallpaper = self.logo.text(), self.wall.text()
        s.login_background, s.grub_background = self.login.text(), self.grub.text()
        s.accent, s.dark = self.accent.color, self.dark.color
        for k, cb in self.opts.items():
            setattr(s, k, cb.isChecked())
        s.grub_timeout, s.kernel_options = self.timeout.value(), self.kopts.text().strip()
        s.validate()
        return s

    def _with_spec(self, func):
        try:
            spec = self.spec()
        except ValueError as e:
            QMessageBox.warning(self, "Distro Branding", str(e))
            return
        self.project.state.setdefault("branding", {})["spec"] = asdict(spec)
        self.project.save()
        func(spec)

    def generate(self):
        self._with_spec(lambda spec: self.task("Generate branding source",
                                               lambda t: DistroBranding(self.project).generate(spec)))

    def apply(self):
        keyring, email = self.with_keyring.isChecked(), self.email.text().strip()
        self._with_spec(lambda spec: self.task(
            "Apply distro branding",
            lambda t: DistroBranding(self.project).apply(spec, with_keyring=keyring, email=email),
            lambda debs: QMessageBox.information(self, "Distro Branding", "Installed:\n" + "\n".join(
                str(d).split("/")[-1] for d in debs))))

    def build_installed(self):
        proj = self.project

        def work(t):
            db = DistroBranding(proj)
            debs = db.build()
            db.install(debs)
            return debs
        self.task("Build edited branding packages", work)

    def create_key(self):
        email = self.email.text().strip()
        self._with_spec(lambda spec: self.task("Create signing key",
                                               lambda t: DistroBranding(self.project).generate_key(spec, email)))

    def export_key(self, secret):
        db = self._db()
        if not db.key_fingerprint():
            QMessageBox.information(self, "Key", "Create a key first.")
            return
        name = "{}-archive-key.{}".format(db.spec().os_id, "secret.asc" if secret else "gpg")
        path, _ = QFileDialog.getSaveFileName(self, "Export key", name)
        if path:
            db.export_key(path, secret=secret)
            self.main.stage_label.setText("Key exported to " + path)
