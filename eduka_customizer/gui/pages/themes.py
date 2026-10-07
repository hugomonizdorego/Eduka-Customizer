"""Themes & Icons page: system-wide look for every new user."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QGridLayout, QLineEdit, QListWidgetItem,
                                          QListWidget)

from eduka_customizer.core.themes import THEME_PACKS, Themes
from eduka_customizer.gui.widgets import DropZone, Page, button, combo, hbox, label

KINDS = {"icons": "Icons", "gtk": "GTK theme", "cursor": "Cursor", "font": "Font", "qt": "Qt",
         "compositor": "Effects"}


class ThemesPage(Page):
    title = "Themes & Icons"
    subtitle = ("Choose the default GTK theme, icons, mouse cursor and font for Eduka-Desktop/LXQt, "
                "Xfce, KDE, GNOME, Cinnamon and MATE. Add your own themes by drag and drop, or install "
                "theme packs with one click.")
    icon_names = ("preferences-desktop-icons", "preferences-desktop-theme")

    def build(self):
        c = self.card("Add your own themes, icons, cursors and fonts",
                      "Drop them here: folders, archives (.zip, .tar.gz, .tar.xz) or files (.ttf, .otf, "
                      ".deb). Eduka-Customizer recognizes each one and puts it where it belongs: themes in "
                      "/usr/share/themes, icons and cursors in /usr/share/icons, fonts in /usr/share/fonts, "
                      "wallpapers in the wallpaper gallery, Plymouth and SDDM themes in theirs.")
        self.drop = DropZone("Drop themes, icon or cursor themes, fonts, wallpapers or their archives here",
                             "Themes and fonts (*.zip *.tar *.tar.gz *.tgz *.tar.xz *.txz *.tar.bz2 *.ttf *.otf "
                             "*.ttc *.deb *.png *.jpg *.jpeg *.svg *.webp *.plymouth);;All files (*)")
        self.drop.dropped.connect(self.add_assets)
        c.add(self.drop)
        self.added = label("", "muted")
        c.add(self.added)

        c = self.card("Install theme packs", "Availability is checked for the Debian suite of the image.")
        self.packs = QListWidget()
        self.packs.setMinimumHeight(220)
        for pkg, kind, text in THEME_PACKS:
            it = QListWidgetItem("{:<12} {}  ({})".format(KINDS.get(kind, kind), text, pkg))
            it.setData(Qt.ItemDataRole.UserRole, pkg)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.packs.addItem(it)
        c.add(self.packs)
        c.add(hbox(None, button("Install ticked packs", self.install_packs, "primary")))

        c = self.card("Default look")
        f = c.form()
        self.gtk = combo([], editable=True)
        self.icons = combo([], editable=True)
        self.cursor = combo([], editable=True)
        self.lxqt = combo([], editable=True)
        self.font = QLineEdit()
        self.font.setPlaceholderText("e.g. Noto Sans 10")
        self.dark = QCheckBox("Prefer dark style")
        f.addRow("GTK theme:", self.gtk)
        f.addRow("Icon theme:", self.icons)
        f.addRow("Cursor theme:", self.cursor)
        f.addRow("LXQt / Eduka theme:", self.lxqt)
        f.addRow("Font:", self.font)
        f.addRow("", self.dark)
        c.add(hbox(button("Fine-tune in the live session", lambda: self.main.go("TerminalPage")), None,
                   button("Apply look", self.apply, "primary")))

        c = self.card("Desktop icons", "Icons shown on the desktop (Eduka-Desktop/LXQt and Xfce).")
        grid = QGridLayout()
        self.di = {}
        for i, (key, text) in enumerate((("home", "Home folder"), ("trash", "Trash"),
                                         ("computer", "Computer"), ("network", "Network"))):
            cb = QCheckBox(text)
            cb.setChecked(key != "network")
            self.di[key] = cb
            grid.addWidget(cb, 0, i)
        c.add(grid)
        c.add(hbox(None, button("Apply desktop icons", self.apply_icons)))

    def refresh(self):
        if not self.project:
            return
        th = Themes(self.project)
        cur = th.current()
        for w, items, val in ((self.gtk, th.gtk_themes(), cur["gtk"]), (self.icons, th.icon_themes(), cur["icons"]),
                              (self.cursor, th.cursor_themes(), cur["cursor"]),
                              (self.lxqt, th.lxqt_themes(), self.project.state.get("themes", {}).get("lxqt", ""))):
            w.clear()
            w.addItems([""] + items)
            w.setCurrentText(val or "")
        self.font.setText(cur["font"])
        self.dark.setChecked(cur["dark"])

    def install_packs(self):
        pkgs = [self.packs.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.packs.count())
                if self.packs.item(i).checkState() == Qt.CheckState.Checked]
        if not pkgs:
            return
        proj = self.project

        def done(result):
            ok, missing = result
            msg = "Installed: {}".format(", ".join(ok) or "nothing")
            if missing:
                msg += "\nNot available for this suite: " + ", ".join(missing)
            self.main.stage_label.setText(msg.replace("\n", " · "))
        self.task("Install theme packs", lambda t: Themes(proj).install_packs(pkgs), done)

    def add_assets(self, paths):
        from eduka_customizer.core.assets import KIND_LABEL, Assets
        proj = self.project

        def done(added):
            self.added.setText("Added: " + ", ".join("{} ({})".format(n, KIND_LABEL.get(k, k)) for k, n in added))
            self.refresh()
        self.task("Add themes and fonts", lambda t: Assets(proj).add(paths), done)

    def apply(self):
        proj = self.project
        vals = (self.gtk.currentText().strip(), self.icons.currentText().strip(), self.cursor.currentText().strip(),
                self.font.text().strip(), self.dark.isChecked(), self.lxqt.currentText().strip())
        self.task("Apply look", lambda t: Themes(proj).apply(*vals))

    def apply_icons(self):
        Themes(self.project).desktop_icons(**{k: cb.isChecked() for k, cb in self.di.items()})
        self.main.stage_label.setText("Desktop icons saved")
