"""Calamares page: installer branding, images, slideshow, users and passwords,
partitions, requirements and the raw configuration files."""

from eduka_customizer.qt.widgets import (QCheckBox, QDoubleSpinBox, QFileDialog, QLineEdit, QListWidget,
                                          QMessageBox, QSpinBox)

from eduka_customizer.core import calamares as cal
from eduka_customizer.gui.pages.appearance import IMAGES, ColorButton
from eduka_customizer.gui.widgets import FilePicker, FileTreeEditor, ImagePreview, Page, button, combo, hbox, label

COLORS = [("sidebarBackground", "Sidebar", "#0f2f27"), ("sidebarText", "Sidebar text", "#ffffff"),
          ("sidebarBackgroundCurrent", "Current step", "#00a879"), ("sidebarTextCurrent", "Current step text", "#ffffff")]


class CalamaresPage(Page):
    title = "Calamares Installer"
    nav_title = "Calamares"
    subtitle = ("Change the graphical installer directly: name, logo and images, colors, the slideshow "
                "shown while installing, user and password rules, partitioning, requirements, and every "
                "configuration file. Test the result by booting the ISO in QEMU (Build & Test).")
    icon_names = ("calamares", "system-software-install", "drive-harddisk")

    def build(self):
        c = self.card("Installer")
        self.state = label("", "muted")
        self.brand_combo = combo([])
        c.add(self.state)
        c.add(hbox(label("Branding in use"), self.brand_combo, button("Use", self.use_branding), None,
                   button("Install Calamares", self.install, "primary")))

        # Branding -------------------------------------------------------------------
        c = self.card("Name, images and colors",
                      "Images are converted to PNG in the right size. Distro Branding creates a complete "
                      "branding of its own; edits here change the branding in use.")
        f = c.form()
        self.s = {}
        for key, text in (("productName", "Product name"), ("shortProductName", "Short name"),
                          ("version", "Version"), ("productUrl", "Home page"), ("supportUrl", "Support URL"),
                          ("knownIssuesUrl", "Known issues URL"), ("releaseNotesUrl", "Release notes URL")):
            self.s[key] = QLineEdit()
            f.addRow(text + ":", self.s[key])
        self.img = {}
        self.prev = {}
        for key, text in (("productLogo", "Logo"), ("productIcon", "Window icon"), ("productWelcome", "Welcome image")):
            self.img[key] = FilePicker(text, IMAGES)
            self.prev[key] = ImagePreview(90, 60)
            self.img[key].changed.connect(lambda p, k=key: self.prev[k].show_file(p))
            f.addRow(text + ":", hbox(self.img[key], self.prev[key]))
        self.colors = {}
        row = []
        for key, text, default in COLORS:
            self.colors[key] = ColorButton(default)
            row += [label(text), self.colors[key]]
        f.addRow("Colors:", hbox(*row, None))
        self.launcher = QLineEdit()
        self.launcher.setPlaceholderText("e.g. Install Edukasaun OS")
        f.addRow("Desktop launcher:", self.launcher)
        c.add(hbox(None, button("Apply name, images and colors", self.apply_branding, "primary")))

        c = self.card("Slideshow while installing", "One image per slide (PNG, JPG, SVG); 800×440 works best.")
        self.slides = QListWidget()
        self.slides.setMaximumHeight(140)
        c.add(self.slides)
        self.seconds = QSpinBox()
        self.seconds.setRange(2, 60)
        self.seconds.setValue(8)
        c.add(hbox(button("Add images...", self.add_slides), button("Remove", self.remove_slide, "danger"),
                   button("Up", lambda: self.move_slide(-1)), button("Down", lambda: self.move_slide(1)),
                   label("Seconds per slide"), self.seconds, None,
                   button("Apply slideshow", self.apply_slides, "primary")))

        # Users ---------------------------------------------------------------------------
        a, b = self.row(self.card("Users and passwords"), self.card("Live session"))
        f = a.form()
        self.autologin = QCheckBox("Log in automatically (default of the checkbox)")
        self.root_pw = QCheckBox("Ask for a root password")
        self.reuse = QCheckBox("Offer 'use the same password for root'")
        self.weak = QCheckBox("Allow weak passwords")
        self.weak_default = QCheckBox("'Allow weak passwords' ticked by default")
        for w in (self.autologin, self.root_pw, self.reuse, self.weak, self.weak_default):
            f.addRow("", w)
        self.minlen = QSpinBox()
        self.minlen.setRange(0, 64)
        self.maxlen = QSpinBox()
        self.maxlen.setRange(-1, 512)
        self.maxlen.setSpecialValueText("no limit")
        f.addRow("Password length:", hbox(label("min"), self.minlen, label("max"), self.maxlen, None))
        self.groups = QLineEdit()
        f.addRow("User groups:", self.groups)
        self.sudo = QLineEdit()
        f.addRow("Administrator group:", self.sudo)
        self.shell = combo(["/bin/bash", "/bin/sh", "/usr/bin/zsh", "/usr/bin/fish"], editable=True)
        f.addRow("Shell:", self.shell)
        self.hostname = QLineEdit()
        self.hostname.setPlaceholderText("${first}-${product}  or  ${first}-${cpu}")
        f.addRow("Computer name:", self.hostname)
        a.add(hbox(None, button("Apply user settings", self.apply_users, "primary")))

        b.add(label("Debian's live user logs in automatically; its password is 'live' (needed for sudo "
                    "or the lock screen). Set another one here, or leave it empty for Debian's default.",
                    "muted"))
        self.live_pw = QLineEdit()
        self.live_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.live_pw.setPlaceholderText("new live password")
        self.live_pw_state = label("", "muted")
        b.add(self.live_pw)
        b.add(self.live_pw_state)
        b.add(hbox(button("Use Debian default", lambda: self.set_live_password("")), None,
                   button("Set live password", lambda: self.set_live_password(self.live_pw.text()), "primary")))

        # Partitions -------------------------------------------------------------------------
        c = self.card("Partitions")
        f = c.form()
        self.initial = combo(cal.PARTITION_CHOICES)
        f.addRow("Preselected option:", self.initial)
        self.fs = combo(cal.FILESYSTEMS)
        f.addRow("Default file system:", self.fs)
        self.fs_allowed = {}
        for name in cal.FILESYSTEMS:
            self.fs_allowed[name] = QCheckBox(name)
        f.addRow("File systems offered:", hbox(*self.fs_allowed.values(), None))
        self.swap = {}
        for key, text in cal.SWAP_CHOICES:
            self.swap[key] = QCheckBox(text)
        f.addRow("Swap choices:", hbox(*self.swap.values(), None))
        self.initial_swap = combo(cal.SWAP_CHOICES)
        f.addRow("Default swap:", self.initial_swap)
        self.efi = combo(["300MiB", "512MiB", "1GiB"], editable=True)
        f.addRow("EFI partition size:", self.efi)
        self.luks = QCheckBox("Offer disk encryption")
        self.luks2 = QCheckBox("Use LUKS2 (GRUB in Debian 13 can unlock it; LUKS1 is the safe choice)")
        f.addRow("", self.luks)
        f.addRow("", self.luks2)
        c.add(hbox(None, button("Apply partition settings", self.apply_partition, "primary")))

        # Requirements and finish --------------------------------------------------------------
        c = self.card("Requirements, boot loader and finish")
        f = c.form()
        self.storage = QDoubleSpinBox()
        self.storage.setRange(1, 500)
        self.storage.setSuffix(" GiB")
        self.ram = QDoubleSpinBox()
        self.ram.setRange(0.25, 64)
        self.ram.setSingleStep(0.25)
        self.ram.setSuffix(" GiB")
        f.addRow("Minimum disk / RAM:", hbox(self.storage, self.ram, None))
        self.internet = QCheckBox("Require an internet connection")
        self.power = QCheckBox("Require a power cable (laptops)")
        f.addRow("", self.internet)
        f.addRow("", self.power)
        self.restart = combo(cal.RESTART_MODES)
        f.addRow("When finished:", self.restart)
        self.boot_timeout = QSpinBox()
        self.boot_timeout.setRange(0, 60)
        f.addRow("GRUB timeout (installed system):", self.boot_timeout)
        self.efi_id = QLineEdit()
        f.addRow("EFI boot entry id:", self.efi_id)
        f.addRow("", label("Keep 'debian' for Secure Boot: Debian's signed GRUB only reads EFI/debian.", "muted"))
        self.removed = QLineEdit()
        f.addRow("Remove after install:", self.removed)
        c.add(hbox(button("Recommended removals", self.recommended_removals), None,
                   button("Apply", self.apply_misc, "primary")))

        c = self.card("All configuration files", "/etc/calamares of the image: settings.conf (module "
                                                 "sequence), modules/*.conf and branding/.")
        self.editor = FileTreeEditor("Select a file, edit it and press 'Save file'.")
        c.add(self.editor)

    # Helpers ------------------------------------------------------------------------
    def calamares(self):
        return cal.Calamares(self.project)

    def refresh(self):
        if not self.project:
            return
        c = self.calamares()
        ok = c.installed()
        self.state.setText("Calamares {} is installed. Branding: {}.".format(c.version() or "", c.branding_name())
                           if ok else "Calamares is not installed in the image. Install it to use this page.")
        self.brand_combo.clear()
        self.brand_combo.addItems(c.brandings())
        self.brand_combo.setCurrentText(c.branding_name())
        self.editor.set_root(c.etc if c.etc.exists() else None)
        if not ok:
            return
        br = c.branding()
        strings = br.get("strings") or {}
        for k, w in self.s.items():
            w.setText(str(strings.get(k, "")))
        style = br.get("style") or {}
        for k, w in self.colors.items():
            if isinstance(style.get(k), str) and style[k].startswith("#") and len(style[k]) == 7:
                w.set(style[k])
        images = br.get("images") or {}
        for k, w in self.img.items():
            path = c.branding_dir() / str(images.get(k, "")) if images.get(k) else None
            self.prev[k].show_file(str(path) if path and path.exists() else "")
            w.setText("")
        self.slides.clear()
        self.slides.addItems(c.slides())
        launcher = c.launcher()
        if launcher:
            import re
            m = re.search(r"(?m)^Name=(.*)$", launcher.read_text(errors="replace"))
            self.launcher.setText(m.group(1) if m else "")
        sm = c.summary()
        u = sm["users"]
        self.autologin.setChecked(u["autologin"])
        self.root_pw.setChecked(u["root_password"])
        self.reuse.setChecked(u["reuse_password"])
        self.weak.setChecked(u["weak"])
        self.weak_default.setChecked(u["weak_default"])
        self.minlen.setValue(u["min_length"])
        self.maxlen.setValue(u["max_length"])
        self.groups.setText(", ".join(u["groups"]))
        self.sudo.setText(u["sudo_group"])
        self.shell.setCurrentText(u["shell"])
        self.hostname.setText(u["hostname"])
        self.live_pw_state.setText("A custom live password is set." if c.live_password_set()
                                   else "Debian default password: live")
        p = sm["partition"]
        self.initial.setCurrentIndex(max(0, self.initial.findData(p["initial"])))
        self.fs.setCurrentIndex(max(0, self.fs.findData(p["fs"])))
        for k, w in self.fs_allowed.items():
            w.setChecked(k in p["filesystems"])
        for k, w in self.swap.items():
            w.setChecked(k in p["swap"])
        self.initial_swap.setCurrentIndex(max(0, self.initial_swap.findData(p["initial_swap"])))
        self.efi.setCurrentText(str(p["efi_size"]))
        self.luks.setChecked(p["luks"])
        self.luks2.setChecked(p["luks2"])
        w = sm["welcome"]
        self.storage.setValue(w["storage"])
        self.ram.setValue(w["ram"])
        self.internet.setChecked(w["internet"])
        self.power.setChecked(w["power"])
        self.restart.setCurrentIndex(max(0, self.restart.findData(sm["finished"]["restart"])))
        try:
            self.boot_timeout.setValue(int(sm["bootloader"]["timeout"] or 5))
        except ValueError:
            self.boot_timeout.setValue(5)
        self.efi_id.setText(sm["bootloader"]["efi_id"])
        self.removed.setText(" ".join(sm["remove"]))

    def _run(self, name, func):
        if not self.calamares().installed():
            QMessageBox.information(self, "Calamares", "Install Calamares first.")
            return
        self.task(name, func, lambda _r: self.refresh())

    # Actions ---------------------------------------------------------------------------
    def install(self):
        proj = self.project
        self.task("Install Calamares", lambda t: cal.Calamares(proj).install(), lambda _r: self.refresh())

    def use_branding(self):
        name = self.brand_combo.currentText()
        if name:
            proj = self.project
            self._run("Use Calamares branding " + name, lambda t: cal.Calamares(proj).use_branding(name))

    def apply_branding(self):
        proj = self.project
        strings = {k: w.text().strip() for k, w in self.s.items()}
        strings["versionedName"] = "{} {}".format(strings["productName"], strings["version"]).strip()
        strings["shortVersionedName"] = "{} {}".format(strings["shortProductName"] or strings["productName"],
                                                       strings["version"]).strip()
        colors = {k: w.color for k, w in self.colors.items()}
        images = {k: w.text() for k, w in self.img.items() if w.text()}
        launcher = self.launcher.text().strip()

        def work(t):
            c = cal.Calamares(proj)
            c.set_branding(strings=strings, colors=colors, images=images)
            if launcher:
                c.set_launcher_name(launcher)
        self._run("Calamares branding", work)

    def add_slides(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Slideshow images", "", IMAGES)
        self.slides.addItems(files)

    def remove_slide(self):
        for it in self.slides.selectedItems():
            self.slides.takeItem(self.slides.row(it))

    def move_slide(self, step):
        row = self.slides.currentRow()
        if row < 0 or not 0 <= row + step < self.slides.count():
            return
        it = self.slides.takeItem(row)
        self.slides.insertItem(row + step, it)
        self.slides.setCurrentRow(row + step)

    def apply_slides(self):
        import shutil
        import tempfile
        proj = self.project
        # Copy first: applying deletes the old slide-NN.png files, which may be in the list.
        tmp = tempfile.mkdtemp(prefix="eduka-slides-")
        files = []
        for i in range(self.slides.count()):
            src = self.slides.item(i).text()
            dst = "{}/{:02d}-{}".format(tmp, i, src.split("/")[-1])
            shutil.copy2(src, dst)
            files.append(dst)
        seconds = self.seconds.value()

        def work(t):
            try:
                cal.Calamares(proj).set_branding(slides=files, slide_seconds=seconds)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        self._run("Calamares slideshow", work)

    def apply_users(self):
        proj = self.project
        kw = dict(autologin=self.autologin.isChecked(), root_password=self.root_pw.isChecked(),
                  reuse_password=self.reuse.isChecked(), min_length=self.minlen.value(),
                  max_length=self.maxlen.value(), weak=self.weak.isChecked(),
                  weak_default=self.weak_default.isChecked(),
                  groups=[g.strip() for g in self.groups.text().replace(",", " ").split() if g.strip()],
                  shell=self.shell.currentText().strip(), sudo_group=self.sudo.text().strip(),
                  hostname=self.hostname.text().strip())
        self._run("Calamares users", lambda t: cal.Calamares(proj).set_users(**kw))

    def set_live_password(self, pw):
        proj = self.project
        self.live_pw.clear()
        self.task("Live user password", lambda t: cal.Calamares(proj).set_live_password(pw),
                  lambda _r: self.refresh())

    def apply_partition(self):
        proj = self.project
        kw = dict(efi_size=self.efi.currentText().strip(), fs=self.fs.currentData(),
                  filesystems=[k for k, w in self.fs_allowed.items() if w.isChecked()],
                  swap=[k for k, w in self.swap.items() if w.isChecked()],
                  initial_swap=self.initial_swap.currentData(), initial=self.initial.currentData(),
                  luks=self.luks.isChecked(), luks2=self.luks2.isChecked())
        self._run("Calamares partitions", lambda t: cal.Calamares(proj).set_partition(**kw))

    def recommended_removals(self):
        self.removed.setText(" ".join(cal.LIVE_PACKAGES))

    def apply_misc(self):
        proj = self.project
        storage, ram = self.storage.value(), self.ram.value()
        internet, power = self.internet.isChecked(), self.power.isChecked()
        restart, timeout = self.restart.currentData(), self.boot_timeout.value()
        efi_id = self.efi_id.text().strip()
        removed = self.removed.text().split()
        if efi_id and efi_id != "debian" and QMessageBox.question(
                self, "Secure Boot", "With an EFI id other than 'debian' the installed system does not boot "
                                     "with Secure Boot enabled. Continue?") != QMessageBox.StandardButton.Yes:
            return

        def work(t):
            c = cal.Calamares(proj)
            c.set_requirements(storage, ram, internet, power)
            c.set_finished(restart)
            c.set_bootloader(timeout, efi_id or None)
            c.set_removed_packages(removed)
        self._run("Calamares requirements and finish", work)
