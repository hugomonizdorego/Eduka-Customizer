"""Wallpaper & Login page (ColorButton and IMAGES are shared with other pages)."""

from eduka_customizer.qt.core import QSize, Qt
from eduka_customizer.qt.gui import QIcon, QPixmap
from eduka_customizer.qt.widgets import QColorDialog, QListWidget, QListWidgetItem, QMessageBox, QPushButton

from eduka_customizer.core.branding import Branding
from eduka_customizer.core.desktop import detect_display_manager
from eduka_customizer.gui.widgets import DropZone, FilePicker, Page, button, combo, hbox, label

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
    title = "Wallpaper & Login"
    nav_title = "Wallpaper & Login"
    subtitle = "A gallery of wallpapers with one default, and the look of the login screen."
    icon_names = ("preferences-desktop-theme", "preferences-desktop-wallpaper")

    def build(self):
        # Wallpaper gallery -----------------------------------------------------------
        a = self.card("Wallpapers", "Add as many wallpapers as you like; every user can choose them in the "
                                    "desktop settings. The one marked ★ is the default of Eduka-Desktop/LXQt, "
                                    "Xfce, KDE, GNOME, Cinnamon and MATE.")
        self.wall_drop = DropZone("Drop pictures or folders of pictures here (PNG, JPEG, WebP, SVG)", IMAGES)
        self.wall_drop.dropped.connect(self.add_wallpapers)
        a.add(self.wall_drop)
        self.gallery = QListWidget()
        self.gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery.setIconSize(QSize(176, 99))
        self.gallery.setGridSize(QSize(196, 135))
        self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.gallery.setMovement(QListWidget.Movement.Static)
        self.gallery.setMinimumHeight(300)
        self.gallery.itemDoubleClicked.connect(lambda _it: self.set_default_wallpaper())
        a.add(self.gallery)
        self.wall_state = label("", "muted")
        a.add(self.wall_state)
        a.add(hbox(button("Remove", self.remove_wallpaper, "danger"), None,
                   button("Make default ★", self.set_default_wallpaper, "primary")))

        b = self.card("Login screen", "")

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

        c = self.card("More", "The boot splash and the ISO boot menu have their own pages.")
        c.add(hbox(button("Plymouth boot splash...", lambda: self.main.go("PlymouthPage")),
                   button("Boot menu of the ISO...", lambda: self.main.go("BootMenuPage")), None))

    def refresh(self):
        if not self.project:
            return
        self.refresh_gallery()
        b = Branding(self.project)
        dm = detect_display_manager(self.project.rootfs)
        self.dm_label.setText("Login manager in the image: <b>{}</b>".format(dm or "none installed"))
        for w, items in ((self.gtk, b.gtk_themes()), (self.icons, b.icon_themes()), (self.sddm, b.login_themes())):
            keep = w.currentText()
            w.clear()
            w.addItems([""] + items)
            w.setCurrentText(keep)

    # Actions ---------------------------------------------------------------------
    def _wall_name(self):
        it = self.gallery.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def refresh_gallery(self):
        from eduka_customizer.core.assets import Wallpapers
        w = Wallpapers(self.project)
        default, keep = w.default(), self._wall_name()
        self.gallery.clear()
        for path in w.list():
            pix = QPixmap(str(path))
            if not pix.isNull():
                pix = pix.scaled(176, 99, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation).copy(0, 0, 176, 99)
            it = QListWidgetItem(QIcon(pix), ("★ " if path.name == default else "") + path.name)
            it.setData(Qt.ItemDataRole.UserRole, path.name)
            it.setToolTip("/" + str(path.relative_to(self.project.rootfs)))
            self.gallery.addItem(it)
            if path.name == (keep or default):
                self.gallery.setCurrentItem(it)
        self.wall_state.setText("{} wallpapers in /{} — default: {}".format(
            self.gallery.count(), w.folder.relative_to(self.project.rootfs), default or "none yet"))

    def add_wallpapers(self, paths):
        from eduka_customizer.core.assets import Wallpapers
        proj = self.project
        self.task("Add wallpapers", lambda t: Wallpapers(proj).add(paths), lambda _r: self.refresh_gallery())

    def set_default_wallpaper(self):
        from eduka_customizer.core.assets import Wallpapers
        name = self._wall_name()
        if name:
            proj = self.project
            self.task("Default wallpaper " + name, lambda t: Wallpapers(proj).set_default(name),
                      lambda _r: self.refresh_gallery())

    def remove_wallpaper(self):
        from eduka_customizer.core.assets import Wallpapers
        name = self._wall_name()
        if name and QMessageBox.question(self, "Remove wallpaper", "Remove {} from the image?".format(name)) == \
                QMessageBox.StandardButton.Yes:
            proj = self.project
            self.task("Remove wallpaper " + name, lambda t: Wallpapers(proj).remove(name),
                      lambda _r: self.refresh_gallery())

    def set_login(self):
        proj = self.project
        bg, logo = self.login_bg.text() or None, self.login_logo.text() or None
        gtk, icons, sddm = self.gtk.currentText(), self.icons.currentText(), self.sddm.currentText()
        self.task("Configure login screen",
                  lambda t: Branding(proj).set_login_screen(bg, gtk, icons, sddm, greeter_logo=logo))
