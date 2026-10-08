"""Themes & Icons page: system-wide look for every new user."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QGridLayout, QLineEdit, QListWidgetItem,
                                          QListWidget)

from eduka_customizer.core import themes as th_core
from eduka_customizer.core.themes import Themes
from eduka_customizer.gui.widgets import DropZone, Page, button, combo, hbox, label

KINDS = {"icons": "Icons", "gtk": "GTK theme", "cursor": "Cursor", "font": "Font", "qt": "Qt style",
         "compositor": "Effects", "xfwm4": "Window theme"}


class ThemesPage(Page):
    title = "Themes & Icons"
    subtitle = ("Choose the default theme, icons, mouse cursor and font. Only what fits the desktop or window "
                "manager of the image is listed. Add your own themes by drag and drop, or install theme packs "
                "with one click.")
    icon_names = ("preferences-desktop-icons", "preferences-desktop-theme")
    CHANGES = ('Apply look', 'Install theme packs')

    def build(self):
        c = self.card("Add your own themes, icons, cursors and fonts",
                      "Drop them here: folders, archives (.zip, .tar.gz, .tar.xz) or files (.ttf, .otf, "
                      ".deb). DistroForge recognizes each one and puts it where it belongs: themes in "
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
        self.for_desktop = label("", "muted")
        c.add(self.for_desktop)
        self.packs = QListWidget()
        self.packs.setMinimumHeight(220)
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
        self.extra = {}
        for key, text in (("xfwm4", "Window theme (Xfwm4):"), ("openbox", "Window theme (Openbox):"),
                          ("cinnamon", "Cinnamon desktop theme:"), ("marco", "Window theme (Marco/Metacity):"),
                          ("plasma", "Plasma global theme:"), ("kvantum", "Kvantum (Qt) theme:")):
            w = combo([], editable=True)
            self.extra[key] = w
            f.addRow(text, w)
        f.addRow("Font:", self.font)
        self.form = f
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

    def _desktop(self):
        from eduka_customizer.core.desktop import DesktopManager
        try:
            return DesktopManager(self.project).current_desktop()
        except Exception:
            return None

    def _set_row(self, widget, visible):
        label_ = self.form.labelForField(widget)
        widget.setVisible(visible)
        if label_:
            label_.setVisible(visible)

    def refresh(self):
        if not self.project:
            return
        th = Themes(self.project)
        de = self._desktop()
        self.for_desktop.setText("Showing what fits <b>{}</b> (step 6. Desktop).".format(de["name"]) if de else
                                 "No desktop chosen yet (step 6. Desktop): every pack is listed.")
        ticked = {self.packs.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.packs.count())
                  if self.packs.item(i).checkState() == Qt.CheckState.Checked}
        self.packs.clear()
        for pack in th_core.packs_catalog():
            if not th_core.pack_fits(pack, de):
                continue
            it = QListWidgetItem("{:<13} {}  ({})".format(KINDS.get(pack["kind"], pack["kind"]), pack["name"],
                                                         pack["package"]))
            it.setData(Qt.ItemDataRole.UserRole, pack["package"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if pack["package"] in ticked else Qt.CheckState.Unchecked)
            self.packs.addItem(it)
        opts = th_core.look_options(de)
        self._set_row(self.lxqt, opts["lxqt"])
        self.form.labelForField(self.gtk).setText("GTK theme (GTK apps):" if opts["gtk_apps_only"] else "GTK theme:")
        saved = self.project.state.get("themes", {})
        for key, w in self.extra.items():
            items = getattr(th, {"xfwm4": "xfwm4_themes", "openbox": "openbox_themes",
                                 "cinnamon": "cinnamon_themes", "marco": "marco_themes",
                                 "plasma": "plasma_looks", "kvantum": "kvantum_themes"}[key])()
            w.clear()
            w.addItems([""] + items)
            w.setCurrentText(saved.get(key, ""))
            self._set_row(w, bool(opts[key]) and (bool(items) or de is not None and opts[key]))
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
        extra = {k: w.currentText().strip() for k, w in self.extra.items() if not w.isHidden()}

        def work(t):
            Themes(proj).apply(*vals)
            if any(extra.values()):
                Themes(proj).apply_extra(**extra)
        self.task("Apply look", work)

    def apply_icons(self):
        Themes(self.project).desktop_icons(**{k: cb.isChecked() for k, cb in self.di.items()})
        self.main.stage_label.setText("Desktop icons saved")
