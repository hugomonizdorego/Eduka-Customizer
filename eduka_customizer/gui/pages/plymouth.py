"""Plymouth page: install boot splash themes from any format, preview, apply, remove."""

from pathlib import Path

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QFileDialog, QLineEdit, QListWidget, QListWidgetItem,
                                          QMessageBox, QSpinBox)

from eduka_customizer.core.plymouth import FORMATS, Plymouth
from eduka_customizer.gui.pages.appearance import ColorButton
from eduka_customizer.gui.widgets import FilePicker, ImagePreview, Page, button, combo, hbox, label


class PlymouthPage(Page):
    title = "Boot Splash (Plymouth)"
    nav_title = "Boot Splash"
    subtitle = ("Step 9 · The animation shown while the computer starts and shuts down: install a theme, preview "
                "it, use it, or make one from your logo. Your changes wait in Review & Apply (step 14).")
    icon_names = ("preferences-desktop-screensaver", "plymouth", "video-display")
    CHANGES = ('Apply Plymouth theme ', 'Create Plymouth theme', 'Install Plymouth', 'Plymouth settings', 'Remove Plymouth theme ')

    def build(self):
        c = self.card("Installed themes")
        self.list = QListWidget()
        self.list.setMinimumHeight(220)
        self.list.currentItemChanged.connect(lambda cur, _p: self.select(cur))
        self.preview = ImagePreview(360, 220)
        self.info = label("", "muted")
        right = hbox(self.preview)
        c.add(hbox(self.list, right))
        c.add(self.info)
        self.seconds = QSpinBox()
        self.seconds.setRange(3, 60)
        self.seconds.setValue(10)
        self.seconds.setSuffix(" s")
        c.add(hbox(button("Remove", self.remove, "danger"), None, label("Preview length"), self.seconds,
                   button("Preview in a window", self.live_preview),
                   button("Apply as boot splash", self.apply, "primary")))

        c = self.card("Install a theme", "Accepted: Debian packages (.deb), archives (.zip, .tar.gz, .tar.xz, "
                                         ".tar.bz2), a theme folder or its .plymouth file. Themes from "
                                         "gnome-look.org / pling usually come as archives.")
        c.add(hbox(button("From file...", self.install_file, "primary"),
                   button("From folder...", self.install_folder), None))
        self.pkg_list = QListWidget()
        self.pkg_list.setMaximumHeight(180)
        c.add(label("Theme packages of Debian:", "muted"))
        c.add(self.pkg_list)
        c.add(hbox(button("Show available packages", self.list_packages), None,
                   button("Install ticked packages", self.install_packages)))

        c = self.card("Create a theme from a logo",
                      "A simple, fast theme: your logo fading in on a colored background with a progress "
                      "bar, a message line and a password prompt for encrypted disks.")
        f = c.form()
        self.gen_name = QLineEdit("my-splash")
        f.addRow("Name:", self.gen_name)
        self.gen_logo = FilePicker("Logo", "PNG images (*.png)")
        self.gen_prev = ImagePreview(160, 90)
        self.gen_logo.changed.connect(lambda p: self.gen_prev.show_file(p))
        f.addRow("Logo (PNG):", hbox(self.gen_logo, self.gen_prev))
        self.gen_bg = ColorButton("#0b3d2e")
        self.gen_fg = ColorButton("#00a879")
        f.addRow("Colors:", hbox(label("Background"), self.gen_bg, label("Progress"), self.gen_fg, None))
        c.add(hbox(None, button("Create and apply", self.generate, "primary")))

        c = self.card("Settings")
        f = c.form()
        self.delay = QSpinBox()
        self.delay.setRange(0, 30)
        self.delay.setSuffix(" s")
        f.addRow("Show after:", self.delay)
        self.scale = combo([("auto", "Automatic"), ("1", "Normal (1x)"), ("2", "HiDPI (2x)")])
        f.addRow("Scale:", self.scale)
        self.iso_splash = QCheckBox("Show the splash when the ISO boots ('quiet splash' in the boot menu)")
        f.addRow("", self.iso_splash)
        c.add(hbox(None, button("Apply settings", self.apply_settings, "primary")))

    # Helpers -------------------------------------------------------------------------
    def ply(self):
        return Plymouth(self.project)

    def _current(self):
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def refresh(self):
        if not self.project:
            return
        p = self.ply()
        keep = self._current()
        self.list.blockSignals(True)
        self.list.clear()
        self._themes = {t["name"]: t for t in p.themes()}
        for t in self._themes.values():
            text = "{}{}   [{}]".format("● " if t["current"] else "", t["title"], t["name"])
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, t["name"])
            self.list.addItem(it)
            if t["name"] == keep or (keep is None and t["current"]):
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        if not self._themes:
            self.info.setText("Plymouth is not installed or has no themes. Install a theme or a package "
                              "below (plymouth is installed automatically).")
        self.select(self.list.currentItem())
        st = p.settings()
        self.delay.setValue(int(float(st["show_delay"] or 0)))
        self.scale.setCurrentIndex(max(0, self.scale.findData(st["device_scale"])))
        params = self.project.state.get("boot", {}).get("extra_params", "quiet splash").split()
        self.iso_splash.setChecked("splash" in params)

    def select(self, item):
        if not item:
            self.preview.show_file("")
            return
        t = self._themes.get(item.data(Qt.ItemDataRole.UserRole), {})
        self.preview.show_file(t.get("preview", ""))
        self.info.setText("<b>{}</b> — {}<br>Type: {} · {}{}".format(
            t.get("title"), t.get("description") or "no description", t.get("module") or "?",
            "package " + t["owner"] if t.get("owner") else "imported theme",
            " · <b>current boot splash</b>" if t.get("current") else ""))

    # Actions ----------------------------------------------------------------------------
    def apply(self):
        name = self._current()
        if name:
            proj = self.project
            self.task("Apply Plymouth theme " + name, lambda t: Plymouth(proj).apply(name),
                      lambda _r: self.refresh())

    def remove(self):
        name = self._current()
        if not name or QMessageBox.question(self, "Remove theme", "Remove the theme {}?".format(name)) != \
                QMessageBox.StandardButton.Yes:
            return
        proj = self.project
        self.task("Remove Plymouth theme " + name, lambda t: Plymouth(proj).remove(name), lambda _r: self.refresh())

    def live_preview(self):
        name = self._current()
        if not name:
            return
        if self.main.live and self.main.live.running:
            QMessageBox.information(self, "Preview", "Stop the live session first.")
            return
        proj, seconds = self.project, self.seconds.value()
        self.task("Preview " + name, lambda t: Plymouth(proj).preview(name, seconds))

    def _install(self, src):
        proj = self.project

        def work(t):
            p = Plymouth(proj)
            with p.chroot:
                p.branding.ensure_plymouth()
            return p.install(src)
        self.task("Install Plymouth theme", work, lambda name: self._after_install(name))

    def _after_install(self, name):
        self.refresh()
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentRow(i)

    def install_file(self):
        src, _ = QFileDialog.getOpenFileName(self, "Plymouth theme", "", FORMATS + ";;All files (*)")
        if src:
            self._install(src)

    def install_folder(self):
        src = QFileDialog.getExistingDirectory(self, "Plymouth theme folder")
        if src:
            self._install(src)

    def list_packages(self):
        proj = self.project

        def done(rows):
            self.pkg_list.clear()
            for name, desc, installed in rows:
                it = QListWidgetItem("{} — {}{}".format(name, desc, "  (installed)" if installed else ""))
                it.setData(Qt.ItemDataRole.UserRole, name)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Unchecked)
                self.pkg_list.addItem(it)
        self.task("List Plymouth theme packages", lambda t: Plymouth(proj).packages(), done)

    def install_packages(self):
        names = [self.pkg_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.pkg_list.count())
                 if self.pkg_list.item(i).checkState() == Qt.CheckState.Checked]
        if names:
            proj = self.project
            self.task("Install Plymouth packages", lambda t: Plymouth(proj).install_packages(names),
                      lambda _r: self.refresh())

    def generate(self):
        logo = self.gen_logo.text()
        if not logo or not Path(logo).is_file():
            QMessageBox.information(self, "Plymouth", "Choose a PNG logo first.")
            return
        proj, name, bg, fg = self.project, self.gen_name.text().strip(), self.gen_bg.color, self.gen_fg.color

        def work(t):
            p = Plymouth(proj)
            with p.chroot:
                p.branding.ensure_plymouth()
                p.apply(p.branding.generate_plymouth(name, logo, bg, fg))
        self.task("Create Plymouth theme", work, lambda _r: self.refresh())

    def apply_settings(self):
        p = self.project
        boot = p.state.setdefault("boot", {})
        params = [x for x in boot.get("extra_params", "quiet splash").split() if x != "splash"]
        if self.iso_splash.isChecked():
            if "quiet" not in params:
                params.insert(0, "quiet")
            params.append("splash")
        boot["extra_params"] = " ".join(params)
        p.state.setdefault("build", {})["boot_params"] = boot["extra_params"]
        p.save()
        if p.has_isotree():
            from eduka_customizer.core import bootloader
            bootloader.update_params(p, boot["extra_params"])
        delay, scale = self.delay.value(), self.scale.currentData()
        self.task("Plymouth settings", lambda t: Plymouth(p).set_settings(delay, scale))
