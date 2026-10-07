"""Wallpaper & Login page (ColorButton and IMAGES are shared with other pages)."""

from eduka_customizer.qt.widgets import QColorDialog, QPushButton

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
    title = "Wallpaper & Login"
    nav_title = "Wallpaper & Login"
    subtitle = "Default wallpaper of every desktop and the look of the login screen."
    icon_names = ("preferences-desktop-theme", "preferences-desktop-wallpaper")

    def build(self):
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

        c = self.card("More", "The boot splash and the ISO boot menu have their own pages.")
        c.add(hbox(button("Plymouth boot splash...", lambda: self.main.go("PlymouthPage")),
                   button("Boot menu of the ISO...", lambda: self.main.go("BootMenuPage")), None))

    def refresh(self):
        if not self.project:
            return
        b = Branding(self.project)
        dm = detect_display_manager(self.project.rootfs)
        self.dm_label.setText("Login manager in the image: <b>{}</b>".format(dm or "none installed"))
        for w, items in ((self.gtk, b.gtk_themes()), (self.icons, b.icon_themes()), (self.sddm, b.login_themes())):
            keep = w.currentText()
            w.clear()
            w.addItems([""] + items)
            w.setCurrentText(keep)

    # Actions ---------------------------------------------------------------------
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
