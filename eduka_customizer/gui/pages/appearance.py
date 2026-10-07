"""Appearance page: Plymouth, wallpaper, login screen and boot menu."""

from pathlib import Path

from eduka_customizer.qt.widgets import QColorDialog, QFileDialog, QLineEdit, QMessageBox, QPushButton, QSpinBox

from eduka_customizer.core import bootloader
from eduka_customizer.core.branding import Branding
from eduka_customizer.core.desktop import detect_display_manager
from eduka_customizer.gui.widgets import FilePicker, ImagePreview, Page, button, combo, hbox, label

IMAGES = "Images (*.png *.jpg *.jpeg *.svg *.webp)"


class ColorButton(QPushButton):
    def __init__(self, color):
        super().__init__()
        self.set(color)
        self.clicked.connect(self.pick)

    def set(self, color):
        self.color = color
        self.setText(color)
        self.setStyleSheet("background: {0}; color: white; border-radius: 8px; padding: 6px 12px;".format(color))

    def pick(self):
        from eduka_customizer.qt.gui import QColor
        c = QColorDialog.getColor(QColor(self.color), self, "Choose color")
        if c.isValid():
            self.set(c.name())


class AppearancePage(Page):
    title = "Appearance"
    subtitle = "Boot splash (Plymouth), wallpaper, login screen and the boot menu of the ISO."
    icon_names = ("preferences-desktop-theme", "preferences-desktop-wallpaper")

    def build(self):
        # Plymouth --------------------------------------------------------------
        c = self.card("Boot splash (Plymouth)",
                      "Shown while the system starts. The initramfs is rebuilt during the next ISO build.")
        f = c.form()
        self.ply = combo([])
        self.ply_state = label("", "muted")
        f.addRow("Theme:", hbox(self.ply, button("Use this theme", self.set_plymouth, "primary")))
        f.addRow("", self.ply_state)
        f.addRow("Import:", hbox(button("Theme folder...", lambda: self.import_plymouth(True)),
                                 button("Theme archive (.tar.gz / .zip)...", lambda: self.import_plymouth(False)),
                                 None))
        self.gen_name = QLineEdit("edukasaun")
        self.gen_logo = FilePicker("Logo", "PNG images (*.png)")
        self.gen_logo.changed.connect(lambda p: self.gen_preview.show_file(p))
        self.gen_bg = ColorButton("#0b3d2e")
        self.gen_fg = ColorButton("#00a879")
        self.gen_preview = ImagePreview(160, 90)
        f.addRow("Create theme:", self.gen_name)
        f.addRow("Logo (PNG):", self.gen_logo)
        f.addRow("Colors:", hbox(label("Background"), self.gen_bg, label("Progress"), self.gen_fg, None,
                                 self.gen_preview))
        c.add(hbox(None, button("Create and use theme", self.generate_plymouth)))

        # Wallpaper -------------------------------------------------------------------
        a, b = self.row(self.card("Wallpaper", "Default desktop background for Eduka-Desktop/LXQt, "
                                               "Xfce, KDE, GNOME, Cinnamon and MATE."),
                        self.card("Login screen", ""))
        self.wall = FilePicker("Wallpaper", IMAGES)
        self.wall_prev = ImagePreview()
        self.wall.changed.connect(lambda p: self.wall_prev.show_file(p))
        a.add(self.wall)
        a.add(hbox(self.wall_prev, None))
        a.add(hbox(None, button("Apply wallpaper", self.set_wallpaper, "primary")))

        self.dm_label = label("", "muted")
        b.add(self.dm_label)
        f = b.form()
        self.login_bg = FilePicker("Login background", IMAGES)
        self.login_logo = FilePicker("Logo / user image", IMAGES)
        self.gtk = combo([""], editable=True)
        self.icons = combo([""], editable=True)
        self.sddm = combo([""])
        f.addRow("Background:", self.login_bg)
        f.addRow("Logo:", self.login_logo)
        f.addRow("GTK theme:", self.gtk)
        f.addRow("Icon theme:", self.icons)
        f.addRow("SDDM theme:", self.sddm)
        b.add(hbox(None, button("Apply login screen", self.set_login, "primary")))

        # Boot menu --------------------------------------------------------------------
        c = self.card("ISO boot menu", "Title, timeout, kernel options and background of the "
                                       "GRUB (UEFI) and ISOLINUX (BIOS) menus.")
        f = c.form()
        self.boot_title = QLineEdit()
        f.addRow("Menu title:", self.boot_title)
        self.timeout = QSpinBox()
        self.timeout.setRange(0, 120)
        f.addRow("Timeout (seconds):", self.timeout)
        self.params = QLineEdit()
        self.params.setPlaceholderText("quiet splash")
        f.addRow("Kernel options:", self.params)
        self.kernel = combo([])
        f.addRow("Kernel:", self.kernel)
        self.splash = FilePicker("Boot menu background", "PNG images (*.png)")
        f.addRow("Background:", self.splash)
        c.add(hbox(button("Edit boot files...", lambda: self.main.go("TerminalPage")), None,
                   button("Apply to boot menu", self.apply_boot, "primary")))
        c.add(label("Live boot options you may add: toram, nomodeset, locales=pt_PT.UTF-8, "
                    "keyboard-layouts=pt, timezone=Asia/Dili, noautologin.", "muted"))

    def refresh(self):
        if not self.project:
            return
        b = Branding(self.project)
        themes = b.plymouth_themes()
        cur = b.plymouth_current()
        self.ply.clear()
        self.ply.addItems(themes)
        if cur in themes:
            self.ply.setCurrentText(cur)
        self.ply_state.setText("Current theme: {}".format(cur or "none (Plymouth not installed?)"))
        dm = detect_display_manager(self.project.rootfs)
        self.dm_label.setText("Login manager in the image: <b>{}</b>".format(dm or "none installed"))
        for w, items in ((self.gtk, b.gtk_themes()), (self.icons, b.icon_themes()), (self.sddm, b.login_themes())):
            keep = w.currentText()
            w.clear()
            w.addItems([""] + items)
            w.setCurrentText(keep)
        boot = self.project.state.get("boot", {})
        self.boot_title.setText(boot.get("title") or self.project.state["identity"].get("name", "Edukasaun OS"))
        self.timeout.setValue(int(boot.get("timeout", 10)))
        self.params.setText(boot.get("extra_params", "quiet splash"))
        from eduka_customizer.core.cleanup import kernels
        ks = kernels(self.project.rootfs)
        self.kernel.clear()
        self.kernel.addItem("Newest installed", "")
        for k in reversed(ks):
            self.kernel.addItem(k, k)
        if boot.get("kernel") and self.kernel.findData(boot["kernel"]) >= 0:
            self.kernel.setCurrentIndex(self.kernel.findData(boot["kernel"]))
        self.splash.setText(boot.get("splash", ""))

    # Actions ---------------------------------------------------------------------
    def set_plymouth(self):
        theme = self.ply.currentText()
        if theme:
            proj = self.project
            self.task("Set Plymouth theme", lambda t: Branding(proj).set_plymouth(theme))

    def import_plymouth(self, folder):
        if folder:
            src = QFileDialog.getExistingDirectory(self, "Plymouth theme folder")
        else:
            src, _ = QFileDialog.getOpenFileName(self, "Plymouth theme archive", "",
                                                 "Archives (*.tar *.tar.gz *.tgz *.tar.xz *.zip)")
        if not src:
            return
        proj = self.project

        def work(t):
            b = Branding(proj)
            b.set_plymouth(b.import_plymouth(src))
        self.task("Import Plymouth theme", work)

    def generate_plymouth(self):
        logo = self.gen_logo.text()
        if not logo or not Path(logo).is_file():
            QMessageBox.information(self, "Plymouth", "Choose a PNG logo first.")
            return
        proj, name, bg, fg = self.project, self.gen_name.text().strip(), self.gen_bg.color, self.gen_fg.color

        def work(t):
            b = Branding(proj)
            with b.chroot:
                b.ensure_plymouth()
                b.set_plymouth(b.generate_plymouth(name, logo, bg, fg))
        self.task("Create Plymouth theme", work)

    def set_wallpaper(self):
        img = self.wall.text()
        if img:
            proj = self.project
            self.task("Set wallpaper", lambda t: Branding(proj).set_wallpaper(img))

    def set_login(self):
        proj = self.project
        bg, logo = self.login_bg.text() or None, self.login_logo.text() or None
        gtk, icons, sddm = self.gtk.currentText(), self.icons.currentText(), self.sddm.currentText()
        self.task("Configure login screen",
                  lambda t: Branding(proj).set_login_screen(bg, gtk, icons, sddm, greeter_logo=logo))

    def apply_boot(self):
        p = self.project
        boot = p.state.setdefault("boot", {})
        boot.update({"title": self.boot_title.text().strip(), "timeout": self.timeout.value(),
                     "extra_params": self.params.text().strip(), "kernel": self.kernel.currentData() or ""})
        splash = self.splash.text()
        if splash:
            boot["splash"] = splash
        p.state["identity"]["name"] = p.state["identity"].get("name") or boot["title"]
        build = p.state.setdefault("build", {})
        build.update({"title": boot["title"] or p.state["identity"].get("name", "Edukasaun OS"),
                      "timeout": boot["timeout"], "boot_params": boot["extra_params"]})
        p.save()
        if p.has_isotree():
            bootloader.set_titles(p.isodir, build["title"])
            bootloader.set_timeout(p.isodir, boot["timeout"])
            bootloader.append_params(p.isodir, boot["extra_params"])
            if splash:
                bootloader.set_splash(p.isodir, splash)
        p.record("boot-menu", build["title"])
        self.main.stage_label.setText("Boot menu settings saved (applied on the next build)")
