"""GRUB Design page: third-party GRUB themes (checked, refused when GRUB could not
show them), the menu designer, and the boot loader of installed systems."""

import copy

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QButtonGroup, QCheckBox, QGridLayout, QListWidget,
                                          QListWidgetItem, QMessageBox, QRadioButton, QSpinBox)

from eduka_customizer.core import bootchoice, grubmenu, grubtheme
from eduka_customizer.gui.widgets import DropZone, Page, button, combo, hbox, label


class GrubDesignPage(Page):
    title = "GRUB Design"
    nav_title = "GRUB Design"
    subtitle = ("Step 8 · A GRUB theme for the boot menu (checked first), the menu entries, and the boot loader "
                "the installer puts on computers. Your changes wait in Review & Apply (step 14).")
    icon_names = ("grub-customizer", "preferences-desktop-theme")
    CHANGES = ('Boot loader ',)

    def build(self):
        c = self.card("GRUB theme",
                      "A theme folder or archive with theme.txt (for example from gnome-look.org or a theme's "
                      "GitHub page). It is used by the GRUB menu of the ISO (UEFI) and, if you like, of installed "
                      "systems. The BIOS menu of the ISO is ISOLINUX: it keeps its background (Boot Menu tab).")
        drop = DropZone("Drop a GRUB theme folder or archive (.zip, .tar.gz, .tar.xz) here",
                        "GRUB themes (*.zip *.tar *.tar.gz *.tgz *.tar.xz *.txz *.tar.bz2);;All files (*)")
        drop.dropped.connect(self.add_themes)
        c.add(drop)
        self.themes = combo([])
        self.themes.setMinimumWidth(220)
        self.theme_installed = QCheckBox("Also for installed systems (GRUB_THEME)")
        self.theme_installed.setChecked(True)
        c.add(hbox(label("Theme:"), self.themes, self.theme_installed, None,
                   button("Remove theme", self.remove_theme, "danger"),
                   button("Use this theme", self.use_theme, "primary")))
        self.theme_state = label("", "muted")
        c.add(self.theme_state)

        c = self.card("Menu designer",
                      "The entries of the ISO's GRUB menu: rename them (double-click), change the order, remove "
                      "some or add ready-made ones; choose the default entry, the timeout and the colors. Saved "
                      "like a manual edit, so every build keeps it.")
        self.entries = QListWidget()
        self.entries.setMinimumHeight(180)
        self.entries.itemChanged.connect(self._renamed)
        c.add(self.entries)
        self.preset = combo([(k, t) for k, t, _x in grubmenu.PRESETS])
        c.add(hbox(button("Up", lambda: self.move(-1)), button("Down", lambda: self.move(1)),
                   button("Remove", self.remove_entry, "danger"), None, self.preset,
                   button("Add entry", self.add_entry)))
        f = c.form()
        self.default = combo([])
        f.addRow("Default entry:", self.default)
        self.timeout = QSpinBox()
        self.timeout.setRange(0, 120)
        self.timeout.setSuffix(" s")
        f.addRow("Timeout:", self.timeout)
        self.colors = {}
        for key, text, dfg, dbg in (("normal", "Menu text", "white", "black"),
                                    ("highlight", "Selected entry", "black", "light-gray")):
            fg, bg = combo(grubmenu.COLORS, dfg), combo(grubmenu.COLORS, dbg)
            self.colors[key] = (fg, bg)
            f.addRow(text + ":", hbox(fg, label("on"), bg, None))
        self.use_colors = QCheckBox("Set these colors (a theme draws its own)")
        f.addRow("", self.use_colors)
        self.menu_state = label("", "muted")
        c.add(self.menu_state)
        c.add(hbox(button("Reload from the ISO", self.load_menu), None,
                   button("Save the menu", self.save_menu, "primary")))

        c = self.card("Boot loader of installed systems",
                      "What Calamares installs on the computer. Packages come from the Debian archive of the image. "
                      "BIOS computers always get GRUB.")
        grid = QGridLayout()
        self.loader_group = QButtonGroup(self)
        self.loader_buttons = {}
        self.loader_grid = grid
        c.add(grid)
        self.loader_state = label("", "muted")
        c.add(self.loader_state)
        c.add(hbox(None, button("Use this boot loader", self.apply_loader, "primary")))

    # Refresh ------------------------------------------------------------------------
    def refresh(self):
        if not self.project:
            return
        g = grubtheme.GrubThemes(self.project)
        self.themes.clear()
        self.themes.addItems(g.installed())
        cur = g.current()
        if cur:
            self.themes.setCurrentText(cur)
        self.theme_state.setText("In use: <b>{}</b>".format(cur) if cur else "The ISO's own GRUB look is in use.")
        self.load_menu()
        self._loaders()

    def _loaders(self):
        while self.loader_grid.count():
            w = self.loader_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.loader_buttons = {}
        b = bootchoice.BootChoice(self.project)
        current = b.current()
        for i, (lid, name, desc, usable, reason) in enumerate(b.options()):
            rb = QRadioButton("{} — {}".format(name, desc if usable else "not available: " + reason))
            rb.setEnabled(usable)
            rb.setChecked(lid == current)
            self.loader_group.addButton(rb)
            self.loader_buttons[lid] = rb
            self.loader_grid.addWidget(rb, i, 0)
        v = b.calamares_version()
        self.loader_state.setText("Calamares {} in the image. Chosen: {}.".format(
            "{}.{}".format(*v) if v else "(not installed yet)", current))

    # Themes ---------------------------------------------------------------------------
    def add_themes(self, paths):
        proj, inst = self.project, self.theme_installed.isChecked()

        def work(t):
            added, refused = [], []
            for p in paths:
                try:
                    added.append(grubtheme.GrubThemes(proj).add(p, installed_system=inst))
                except grubtheme.ThemeRejected as e:
                    refused.append("{}:\n{}".format(p, e))
            return added, refused

        def done(result):
            added, refused = result
            self.refresh()
            msg = []
            for name, warnings, info in added:
                msg.append("Added {} ({} files{}){}".format(name, info["files"],
                                                           ", background " + info["background"]
                                                           if info.get("background") else "",
                                                           "\n  " + "\n  ".join(warnings) if warnings else ""))
                self.themes.setCurrentText(name)
            if refused:
                QMessageBox.warning(self, "GRUB theme refused", "\n\n".join(refused))
            if msg:
                QMessageBox.information(self, "GRUB theme", "\n".join(msg) + "\n\nPress 'Use this theme'.")
        self.task("Check GRUB theme", work, done)

    def use_theme(self):
        name = self.themes.currentText()
        if name:
            grubtheme.GrubThemes(self.project).use(name, self.theme_installed.isChecked())
            self.refresh()
            self.main.stage_label.setText("GRUB theme {} in use: 'Apply to the ISO now' on the Boot Menu tab, or "
                                          "build".format(name))

    def remove_theme(self):
        grubtheme.GrubThemes(self.project).remove()
        self.refresh()

    # Menu -----------------------------------------------------------------------------
    def load_menu(self):
        d = grubmenu.GrubMenu(self.project).design()
        self._text = grubmenu.GrubMenu(self.project).read()
        self.entries.blockSignals(True)
        self.entries.clear()
        for e in d["entries"]:
            self._add_item(e)
        self.entries.blockSignals(False)
        self._defaults(d["default"])
        try:
            self.timeout.setValue(int(d["timeout"] or 5))
        except ValueError:
            self.timeout.setValue(5)
        for key, value in (("normal", d["normal"]), ("highlight", d["highlight"])):
            if "/" in value:
                fg, bg = value.split("/", 1)
                self.colors[key][0].setCurrentText(fg)
                self.colors[key][1].setCurrentText(bg)
        self.use_colors.setChecked(bool(d["normal"]))
        self.menu_state.setText("{} entries in /boot/grub/grub.cfg".format(self.entries.count()) if self._text
                                else "The ISO has no /boot/grub/grub.cfg yet.")

    def _add_item(self, e):
        it = QListWidgetItem(e["title"])
        it.setData(Qt.ItemDataRole.UserRole, copy.deepcopy(e))
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
        self.entries.addItem(it)
        return it

    def _current_entries(self):
        out = []
        for i in range(self.entries.count()):
            it = self.entries.item(i)
            e = dict(it.data(Qt.ItemDataRole.UserRole))
            e["title"] = it.text().strip() or e["title"]
            out.append(e)
        return out

    def _defaults(self, current=None):
        current = current if current is not None else self.default.currentText()
        self.default.clear()
        titles = [e["title"] for e in self._current_entries()]
        self.default.addItems(titles)
        if current in titles:
            self.default.setCurrentText(current)

    def _renamed(self, _item):
        self._defaults()

    def move(self, step):
        row = self.entries.currentRow()
        if row < 0 or not 0 <= row + step < self.entries.count():
            return
        it = self.entries.takeItem(row)
        self.entries.insertItem(row + step, it)
        self.entries.setCurrentRow(row + step)

    def remove_entry(self):
        for it in self.entries.selectedItems():
            self.entries.takeItem(self.entries.row(it))
        self._defaults()

    def add_entry(self):
        try:
            e = grubmenu.preset_entry(self._text, self.preset.currentData())
        except (ValueError, StopIteration) as err:
            QMessageBox.warning(self, "GRUB menu", str(err))
            return
        self.entries.setCurrentItem(self._add_item(e))
        self._defaults()

    def save_menu(self):
        colors = {}
        if self.use_colors.isChecked():
            colors = {k: "{}/{}".format(fg.currentText(), bg.currentText()) for k, (fg, bg) in self.colors.items()}
        try:
            grubmenu.GrubMenu(self.project).save(self._current_entries(), default=self.default.currentText() or None,
                                                 timeout=self.timeout.value(), normal=colors.get("normal"),
                                                 highlight=colors.get("highlight"))
        except ValueError as e:
            QMessageBox.warning(self, "GRUB menu", str(e))
            return
        self.load_menu()
        self.main.stage_label.setText("GRUB menu saved; it is kept for every build")

    # Boot loader -------------------------------------------------------------------------
    def apply_loader(self):
        lid = next((k for k, b in self.loader_buttons.items() if b.isChecked()), None)
        if not lid:
            return
        proj = self.project
        self.task("Boot loader " + lid, lambda t: bootchoice.BootChoice(proj).apply(lid), lambda _r: self._loaders())

    _text = ""
