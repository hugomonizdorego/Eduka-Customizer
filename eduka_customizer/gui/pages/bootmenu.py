"""Boot Menu page: ISO boot menu settings and direct editing of GRUB (BIOS and
UEFI, including the EFI image) and ISOLINUX files, applied to the ISO at once."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.gui import QFont
from eduka_customizer.qt.widgets import (QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                                          QPlainTextEdit, QSpinBox, QSplitter)

from eduka_customizer.core import bootedit, bootloader
from eduka_customizer.core.language import Language
from eduka_customizer.gui.widgets import FilePicker, Page, button, combo, hbox, label


class BootMenuPage(Page):
    title = "Boot Menu of the ISO"
    nav_title = "Boot Menu"
    subtitle = ("What you see when the ISO starts: GRUB for UEFI, ISOLINUX for BIOS. Change the title, "
                "timeout, kernel options and background, or edit grub.cfg, isolinux.cfg and the GRUB file "
                "inside the EFI image directly. Edits are kept for every build and can be applied to the "
                "ISO right away.")
    icon_names = ("grub-customizer", "system-reboot", "media-optical")

    def build(self):
        c = self.card("Menu settings", "Applied to every boot entry of the live system.")
        f = c.form()
        self.boot_title = QLineEdit()
        f.addRow("Menu title:", self.boot_title)
        self.timeout = QSpinBox()
        self.timeout.setRange(0, 120)
        self.timeout.setSuffix(" s")
        f.addRow("Timeout:", self.timeout)
        self.params = QLineEdit()
        self.params.setPlaceholderText("quiet splash")
        f.addRow("Kernel options:", self.params)
        self.kernel = combo([])
        f.addRow("Kernel:", self.kernel)
        self.splash = FilePicker("Boot menu background", "PNG images (*.png)")
        f.addRow("Background:", self.splash)
        c.add(label("Useful live options: toram (run from RAM), nomodeset (graphics problems), "
                    "noautologin, locales=pt_PT.UTF-8, keyboard-layouts=pt, timezone=Asia/Dili.", "muted"))
        self.lang_info = label("", "muted")
        c.add(self.lang_info)
        c.add(hbox(button("Languages...", lambda: self.main.go("LanguagePage")),
                   button("Kernels...", lambda: self.main.go("KernelPage")), None,
                   button("Apply menu settings", self.apply_settings, "primary")))

        c = self.card("Edit boot files")
        split = QSplitter()
        self.files = QListWidget()
        self.files.setMinimumWidth(260)
        self.files.currentItemChanged.connect(lambda cur, _p: self.load(cur))
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("monospace"))
        self.editor.setMinimumHeight(340)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        split.addWidget(self.files)
        split.addWidget(self.editor)
        split.setStretchFactor(1, 3)
        c.add(split)
        self.file_state = label("", "muted")
        c.add(self.file_state)
        self.keep = QCheckBox("Keep this edit on every build (re-applied after the menu is regenerated)")
        self.keep.setChecked(True)
        c.add(self.keep)
        c.add(hbox(button("Check", self.check), button("Revert to original", self.revert, "danger"), None,
                   button("Save", self.save),
                   button("Save and apply to the ISO now", self.save_and_build, "primary")))
        c.add(label("'Apply to the ISO now' rebuilds the ISO in seconds with the system already compressed "
                    "by the last build. Changes inside the system need a full build.", "muted"))

    # Helpers ------------------------------------------------------------------------
    def _key(self):
        it = self.files.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def refresh(self):
        if not self.project:
            return
        p = self.project
        boot = p.state.get("boot", {})
        self.boot_title.setText(boot.get("title") or p.state["identity"].get("name", "Edukasaun OS"))
        self.timeout.setValue(int(boot.get("timeout", 10)))
        self.params.setText(boot.get("extra_params", "quiet splash"))
        from eduka_customizer.core.cleanup import kernels
        self.kernel.clear()
        self.kernel.addItem("Newest installed", "")
        for k in reversed(kernels(p.rootfs)):
            self.kernel.addItem(k, k)
        if boot.get("kernel") and self.kernel.findData(boot["kernel"]) >= 0:
            self.kernel.setCurrentIndex(self.kernel.findData(boot["kernel"]))
        self.splash.setText(boot.get("splash", ""))
        entries = Language(p).boot_entries()
        self.lang_info.setText("Language submenu: " + ", ".join(t for t, _ in entries) if entries
                               else "No language submenu (choose more languages on the Language page).")
        keep = self._key()
        self.files.blockSignals(True)
        self.files.clear()
        overrides = set(bootedit.overrides(p))
        if p.has_isotree():
            for key in bootedit.files(p):
                it = QListWidgetItem(("✎ " if key in overrides else "") + key)
                it.setData(Qt.ItemDataRole.UserRole, key)
                self.files.addItem(it)
                if key == keep:
                    self.files.setCurrentItem(it)
        self.files.blockSignals(False)
        if not self.files.count():
            self.file_state.setText("No ISO tree yet: extract an ISO or build once to get boot files.")
        self.load(self.files.currentItem())

    def load(self, item):
        if not item:
            self.editor.clear()
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        try:
            self.editor.setPlainText(bootedit.read(self.project, key))
        except (OSError, FileNotFoundError) as e:
            self.editor.setPlainText("")
            self.file_state.setText(str(e))
            return
        kept = key in bootedit.overrides(self.project)
        # Ticked unless this file was saved before without "keep".
        self.keep.setChecked(kept or not bootedit.edited(self.project, key))
        self.file_state.setText("{} — {}".format(
            key, "edited by you, re-applied at every build" if kept else "as generated / from the source ISO"))

    # Actions ------------------------------------------------------------------------
    def apply_settings(self):
        p = self.project
        boot = p.state.setdefault("boot", {})
        boot.update({"title": self.boot_title.text().strip(), "timeout": self.timeout.value(),
                     "extra_params": self.params.text().strip(), "kernel": self.kernel.currentData() or ""})
        splash = self.splash.text()
        if splash:
            boot["splash"] = splash
        build = p.state.setdefault("build", {})
        build.update({"title": boot["title"] or p.state["identity"].get("name", "Edukasaun OS"),
                      "timeout": boot["timeout"], "boot_params": boot["extra_params"]})
        p.save()
        if p.has_isotree():
            bootloader.set_titles(p.isodir, build["title"])
            bootloader.set_timeout(p.isodir, boot["timeout"])
            bootloader.update_params(p, boot["extra_params"])
            if splash:
                bootloader.set_splash(p.isodir, splash)
            Language(p).apply_boot_menu(build["title"])
            bootedit.apply_overrides(p)
        p.record("boot-menu", build["title"])
        self.main.stage_label.setText("Boot menu settings saved")
        self.refresh()

    def check(self):
        key = self._key()
        if not key:
            return
        problems = bootedit.validate(self.project, key, self.editor.toPlainText())
        if problems:
            QMessageBox.warning(self, "Check", "\n".join(problems))
        else:
            QMessageBox.information(self, "Check", "No problems found in {}.".format(key))
        return problems

    def save(self, quiet=False):
        key = self._key()
        if not key:
            return False
        text = self.editor.toPlainText()
        problems = bootedit.validate(self.project, key, text)
        if problems and QMessageBox.question(
                self, "Save", "Problems were found:\n\n{}\n\nSave anyway?".format("\n".join(problems))) != \
                QMessageBox.StandardButton.Yes:
            return False
        try:
            bootedit.save(self.project, key, text, keep=self.keep.isChecked())
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.warning(self, "Save", str(e))
            return False
        self.main.stage_label.setText("Saved " + key)
        self.refresh()
        return True

    def save_and_build(self):
        if not self.save():
            return
        from eduka_customizer.core.isobuild import quick_build
        proj = self.project
        self.task("Apply boot menu to the ISO",
                  lambda t: quick_build(proj, progress=t.set_progress, stage=t.set_stage))

    def revert(self):
        key = self._key()
        if key and QMessageBox.question(self, "Revert", "Forget your edits of {}?".format(key)) == \
                QMessageBox.StandardButton.Yes:
            bootedit.revert(self.project, key)
            self.refresh()
