"""Boot Loader page: install or remove boot loaders in the image, choose the one the
installer puts on computers, and set each one up (timeout, kernel options, menu)."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import QCheckBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QSpinBox, QWidget

from eduka_customizer.core import bootchoice
from eduka_customizer.gui.widgets import Page, button, combo, fill, hbox, label, table


class BootLoaderPage(Page):
    title = "Boot Loader"
    nav_title = "Boot Loader"
    subtitle = ("Step 8 · The boot loader the installer puts on computers. Install the ones you want into the "
                "image, remove the others, choose one and set it up. Every choice works with the Calamares "
                "installer; when a boot loader cannot work on a computer, the next one that can is used.")
    icon_names = ("grub-customizer", "system-reboot")
    CHANGES = ("Install boot loader", "Remove boot loader", "Use boot loader")

    def build(self):
        c = self.card("Boot loaders",
                      "Select a boot loader to read about it and to change its settings below.")
        self.list = table(["Boot loader", "Computers", "In the image", "Installer"])
        self.list.setMinimumHeight(250)
        self.list.setSortingEnabled(False)
        self.list.itemSelectionChanged.connect(self._selected)
        c.add(self.list)
        self.about = label("", "muted")
        c.add(self.about)
        self.install_btn = button("Install into the image", self.install)
        self.remove_btn = button("Remove from the image", self.remove, "danger")
        self.use_btn = button("Use for installed systems", self.use, "primary")
        c.add(hbox(self.install_btn, self.remove_btn, None, self.use_btn))

        self.settings_card = self.card("Settings")
        self.settings_title = self.settings_card.findChild(QLabel)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.settings_card.add(self.form_host)
        self.settings_note = label("", "muted")
        self.settings_card.add(self.settings_note)
        self.save_btn = button("Save settings", self.save, "primary")
        self.settings_card.add(hbox(button("Defaults", self.defaults), None, self.save_btn))

        c = self.card("Check", "What the installer will do with the chosen boot loader.")
        self.state = label("", "muted")
        c.add(self.state)
        c.add(hbox(button("GRUB theme and the ISO's boot menu...", lambda: self.main.go("BootMenuPage")), None,
                   button("Check the installer...", lambda: self.main.go("CalamaresPage"))))
        self.widgets = {}
        self._lid = None

    # ------------------------------------------------------------------------------------
    def b(self):
        return bootchoice.BootChoice(self.project)

    def refresh(self):
        if not self.project:
            return
        b = self.b()
        cur = b.current()
        self._rows = b.options()
        keep = self._lid or cur
        self.list.blockSignals(True)
        fill(self.list, [(name, fw or "—", "installed" if inimg else ("not available" if not ok else "—"),
                          "✔ used by the installer" if lid == cur else "")
                         for lid, name, fw, _d, ok, _w, inimg in self._rows], sort=False)
        self.list.blockSignals(False)
        for i in range(3):
            self.list.resizeColumnToContents(i)
        row = next((i for i, r in enumerate(self._rows) if r[0] == keep), 0)
        self.list.selectRow(row)
        self._selected()
        lines = []
        for level, text in b.check():
            lines.append("{} {}".format({"ok": "✔", "warn": "⚠", "fail": "✘"}.get(level, "•"), text))
        v = b.calamares_version()
        lines.append("Calamares {} in the image.".format("{}.{}".format(*v) if v else "is not installed yet"))
        self.state.setText("<br>".join(lines))

    def _row(self):
        rows = sorted({i.row() for i in self.list.selectedIndexes()})
        return self._rows[rows[0]] if rows and rows[0] < len(self._rows) else None

    def _selected(self):
        r = self._row()
        if not r:
            return
        lid, name, fw, desc, ok, why, inimg = r
        known = lid in bootchoice.BY_ID
        self.about.setText("<b>{}</b>{} — {}".format(name, " ({})".format(fw) if fw else "",
                                                   desc if ok or not known else "not available: " + why))
        cur = self.b().current()
        self.install_btn.setEnabled(known and not inimg)
        self.remove_btn.setEnabled(known and inimg and lid != cur)
        self.use_btn.setEnabled(known and ok and lid != cur)
        self.use_btn.setText("Use for installed systems" if lid != cur else "In use for installed systems")
        if known:
            self._lid = lid
            self._form(lid)

    def _form(self, lid):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.widgets = {}
        fid = "grub" if lid == "grub-secureboot" else lid
        lo = bootchoice.loader(fid)
        values = self.b().settings(fid)
        for key, text, kind, _default, choices in lo.fields:
            v = values.get(key)
            if kind == "int":
                w = QSpinBox()
                w.setRange(0, 300)
                w.setSuffix(" s")
                w.setValue(int(v))
            elif kind == "bool":
                w = QCheckBox(text)
                w.setChecked(bool(v))
            elif kind == "choice":
                w = combo(choices, v)
            else:
                w = QLineEdit(str(v or ""))
            self.widgets[key] = (kind, w)
            self.form.addRow("" if kind == "bool" else text + ":", w)
        self.settings_title.setText(
            "Settings: {}".format(lo.name if lid != "grub-secureboot" else "GRUB 2 (also with Secure Boot)"))
        notes = {"grub": "Written to /etc/default/grub.d of the image: the installer and every later update-grub "
                         "use them. The GRUB theme is chosen on the Boot Menu tab.",
                 "systemd-boot": "Written to loader/loader.conf on the EFI partition when the system is installed.",
                 "refind": "Written to refind.conf and /boot/refind_linux.conf when the system is installed.",
                 "efistub": "The kernel options are stored in the firmware's boot entry when the system is "
                            "installed; root= is found by itself.",
                 "syslinux": "Written to /boot/syslinux/syslinux.cfg, again after every kernel update."}
        self.settings_note.setText(notes.get(fid, ""))

    def _values(self):
        out = {}
        for key, (kind, w) in self.widgets.items():
            if kind == "int":
                out[key] = w.value()
            elif kind == "bool":
                out[key] = w.isChecked()
            elif kind == "choice":
                out[key] = w.currentData()
            else:
                out[key] = w.text().strip()
        return out

    # Actions ------------------------------------------------------------------------------------
    def defaults(self):
        if not self._lid:
            return
        fid = "grub" if self._lid == "grub-secureboot" else self._lid
        for key, _t, kind, default, _c in bootchoice.loader(fid).fields:
            k, w = self.widgets[key]
            if k == "int":
                w.setValue(int(default))
            elif k == "bool":
                w.setChecked(bool(default))
            elif k == "choice":
                w.setCurrentIndex(max(0, w.findData(default)))
            else:
                w.setText(str(default))

    def save(self):
        if not self._lid:
            return
        try:
            self.b().configure(self._lid, self._values())
        except (ValueError, OSError, RuntimeError) as e:
            QMessageBox.warning(self, "Boot loader", str(e))
            return
        self.main.stage_label.setText("Boot loader settings saved")
        self.refresh()

    def install(self):
        lid, proj = self._lid, self.project
        self.task("Install boot loader " + bootchoice.loader(lid).name,
                  lambda t: bootchoice.BootChoice(proj).install(lid), lambda _r: self.refresh())

    def remove(self):
        lid, proj = self._lid, self.project
        name = bootchoice.loader(lid).name
        if QMessageBox.question(self, "Boot loader", "Remove {} from the image?".format(name)) \
                != QMessageBox.StandardButton.Yes:
            return
        self.task("Remove boot loader " + name, lambda t: bootchoice.BootChoice(proj).remove(lid),
                  lambda _r: self.refresh())

    def use(self):
        lid, proj = self._lid, self.project
        values = self._values()

        def work(t):
            b = bootchoice.BootChoice(proj)
            b.configure(lid, values, write=False)
            b.use(lid)
        self.task("Use boot loader " + bootchoice.loader(lid).name, work, lambda _r: self.refresh())
