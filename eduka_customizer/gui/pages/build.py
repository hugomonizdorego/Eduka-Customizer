"""Build page: compression, cleanup and boot options, then build and test."""

import shutil
import subprocess
from pathlib import Path

from eduka_customizer.qt.widgets import QCheckBox, QGridLayout, QLineEdit, QMessageBox, QSpinBox

from eduka_customizer.core import cleanup, preflight, qemu
from eduka_customizer.core.isobuild import COMPRESSORS, BuildOptions, build, iso_filename
from eduka_customizer.gui.widgets import FilePicker, Page, button, combo, fill, hbox, label, table


class BuildPage(Page):
    title = "Check & Build"
    nav_title = "Check & Build"
    subtitle = ("Check the image, create the ISO (hybrid BIOS/UEFI, writable to USB) and boot it "
                "in a virtual machine. The build only starts when the checks find no problem.")
    icon_names = ("media-optical-burn", "media-optical", "drive-optical")

    def build(self):
        c = self.card("Check before building",
                      "Finds what would make the build fail, the ISO not boot, or private data leak into it.")
        self.checks = table(["Result", "Check", "Details"])
        self.checks.setMinimumHeight(260)
        self.checks.cellDoubleClicked.connect(self._open_fix)
        c.add(self.checks)
        self.check_state = label("Not checked yet.", "muted", wrap=False)
        c.add(hbox(self.check_state, None, button("Deep check (apt-get check)", lambda: self.run_checks(True)),
                   button("Check now", self.run_checks, "primary")))
        self._results = []

        c = self.card("Image")
        f = c.form()
        self.iso_name = QLineEdit()
        self.iso_name.textChanged.connect(self._preview)
        f.addRow("File name:", self.iso_name)
        self.preview = label("", "muted")
        f.addRow("", self.preview)
        self.label_ = QLineEdit()
        self.label_.setMaxLength(32)
        f.addRow("Volume label:", self.label_)
        self.comp = combo([("zstd", "zstd - fast, good (recommended)"), ("xz", "xz - smallest, slow"),
                           ("gzip", "gzip - most compatible"), ("lz4", "lz4 - fastest, largest"),
                           ("lzo", "lzo")])
        self.comp.currentIndexChanged.connect(self._levels)
        self.level = QSpinBox()
        f.addRow("Compression:", hbox(self.comp, label("Level"), self.level))
        self.boot_mode = combo([("auto", "Automatic"), ("replay", "Keep boot setup of the source ISO"),
                                ("generate", "Generate new boot menu (GRUB + ISOLINUX)")])
        f.addRow("Boot loader:", self.boot_mode)
        self.initramfs = combo([("auto", "Rebuild when needed"), ("always", "Always rebuild"),
                                ("never", "Never rebuild")])
        f.addRow("Initramfs:", self.initramfs)
        self.secure = QCheckBox("Secure Boot (signed shim + GRUB, when generating)")
        self.remove_di = QCheckBox("Remove Debian-Installer entries (Calamares installs the customized system)")
        self.reuse = QCheckBox("Reuse existing filesystem.squashfs (only boot files changed)")
        self.sha512 = QCheckBox("Also write SHA-512 and MD5 checksums")
        for w in (self.secure, self.remove_di, self.reuse, self.sha512):
            f.addRow("", w)

        c = self.card("Clean-up before compressing", "Keeps private data and caches out of the ISO.")
        grid = QGridLayout()
        self.clean = {}
        for i, (key, (text, default)) in enumerate(cleanup.OPTIONS.items()):
            cb = QCheckBox(text)
            cb.setChecked(default)
            self.clean[key] = cb
            grid.addWidget(cb, i // 2, i % 2)
        c.add(grid)

        c = self.card("Last changes before building",
                      "Install more applications or change settings right before the build: everything "
                      "done here goes into this ISO.")
        self.apt_line = QLineEdit()
        self.apt_line.setPlaceholderText("package names to install now, e.g. vlc gimp")
        self.apt_line.returnPressed.connect(self.apt_install)
        c.add(hbox(self.apt_line, button("Install", self.apt_install)))
        c.add(hbox(button("Live desktop / Synaptic / terminal...", lambda: self.main.go("TerminalPage")),
                   button("Kernel...", lambda: self.main.go("KernelPage")),
                   button("Boot menu...", lambda: self.main.go("BootMenuPage")), None))

        c = self.card()
        self.build_btn = button("Build ISO image", self.start_build, "primary", ("media-optical-burn",))
        self.build_btn.setMinimumHeight(42)
        self.quick_btn = button("Rebuild boot files only", self.quick_build,
                                tooltip="Seconds instead of minutes: keeps the compressed system of the last "
                                        "build and only renews the boot menu, kernel and initrd.")
        c.add(hbox(label("Building takes 10-40 minutes depending on size and compression.", "muted"),
                   None, self.quick_btn, self.build_btn))

        c = self.card("Result")
        self.result = label("No image built yet.")
        c.add(self.result)
        c.add(hbox(button("Open output folder", self.open_output), None))

        c = self.card("Test in a virtual machine (QEMU)")
        f = c.form()
        self.test_iso = FilePicker("ISO image", "ISO images (*.iso)")
        f.addRow("ISO:", self.test_iso)
        self.firmware = combo([("uefi", "UEFI"), ("bios", "Legacy BIOS"), ("secureboot", "UEFI + Secure Boot")])
        self.mem = QSpinBox()
        self.mem.setRange(512, 65536)
        self.mem.setSingleStep(512)
        self.mem.setValue(4096)
        self.cpus = QSpinBox()
        self.cpus.setRange(1, 64)
        self.cpus.setValue(2)
        f.addRow("Firmware:", hbox(self.firmware, label("RAM (MiB)"), self.mem, label("CPUs"), self.cpus))
        self.disk = QCheckBox("Attach a virtual hard disk to test installation")
        f.addRow("", self.disk)
        self.kvm_state = label("KVM acceleration: " + ("available" if qemu.kvm_available() else
                                                      "not available (slow)"), "muted")
        f.addRow("", self.kvm_state)
        c.add(hbox(button("Reset test disk", self.reset_disk), None,
                   button("Boot ISO", self.test, "primary", ("media-playback-start",))))

    def _levels(self):
        lo, hi, default, flag = COMPRESSORS[self.comp.currentData()]
        self.level.setEnabled(bool(flag))
        self.level.setRange(lo, max(lo, hi))
        if flag:
            self.level.setValue(default)

    def _preview(self):
        if self.project:
            self.preview.setText("→ {}".format(iso_filename(self.iso_name.text(), self.project)))

    def refresh(self):
        if not self.project:
            return
        o = BuildOptions.from_project(self.project)
        self.iso_name.setText(o.iso_name)
        self.label_.setText(o.volume_label)
        i = self.comp.findData(o.compression)
        self.comp.setCurrentIndex(max(0, i))
        self._levels()
        if COMPRESSORS[o.compression][3]:
            self.level.setValue(int(o.level))
        for w, val in ((self.boot_mode, o.boot_mode), (self.initramfs, o.initramfs)):
            idx = w.findData(val)
            w.setCurrentIndex(max(0, idx))
        self.secure.setChecked(o.secure_boot)
        self.remove_di.setChecked(o.remove_installer)
        self.reuse.setChecked(False)
        self.sha512.setChecked("sha512" in o.checksums)
        for k, cb in self.clean.items():
            cb.setChecked(bool(o.cleanup.get(k, cleanup.OPTIONS[k][1])))
        last = self.project.state.get("last_iso")
        if last and Path(last).exists():
            size = Path(last).stat().st_size / 1024 ** 3
            sha = Path(last + ".sha256")
            digest = sha.read_text().split()[0] if sha.exists() else ""
            self.result.setText("<b>{}</b><br>{:.2f} GiB<br>SHA-256: {}<br><br>Write it to a USB stick "
                                "with: <code>sudo dd if='{}' of=/dev/sdX bs=4M status=progress "
                                "oflag=sync</code>".format(last, size, digest, last))
            if not self.test_iso.text():
                self.test_iso.setText(last)
        self._preview()

    def options(self):
        o = BuildOptions.from_project(self.project)
        o.iso_name = self.iso_name.text().strip() or o.iso_name
        o.volume_label = self.label_.text().strip() or o.volume_label
        o.compression = self.comp.currentData()
        o.level = self.level.value()
        o.boot_mode = self.boot_mode.currentData()
        o.initramfs = self.initramfs.currentData()
        o.secure_boot = self.secure.isChecked()
        o.remove_installer = self.remove_di.isChecked()
        o.reuse_squashfs = self.reuse.isChecked()
        o.checksums = ["sha256", "sha512", "md5"] if self.sha512.isChecked() else ["sha256"]
        o.cleanup = {k: cb.isChecked() for k, cb in self.clean.items()}
        return o

    def start_build(self):
        if self.main.live and self.main.live.running:
            if QMessageBox.question(self, "Build", "Stop the live session and build?") != \
                    QMessageBox.StandardButton.Yes:
                return
            self.main.live.stop()
            self.main.live = None
        opts = self.options()
        self.project.state["identity"]["volume_label"] = opts.volume_label
        self.project.save()
        self.run_checks(then_build=opts)

    def _build(self, opts):
        proj = self.project

        def done(out):
            self.test_iso.setText(str(out))
            self.refresh()
            QMessageBox.information(self, "ISO ready", "Your ISO image is ready:\n{}".format(out))
        self.task("Build ISO", lambda t: build(proj, opts, t.set_progress, t.set_stage), done)

    # Checks -----------------------------------------------------------------------
    MARKS = {"ok": "✔ OK", "info": "ℹ Info", "warn": "⚠ Warning", "fail": "✘ Problem"}

    def run_checks(self, deep=False, then_build=None):
        proj = self.project
        if not proj:
            return

        def done(results):
            self._show_checks(results)
            if then_build is None:
                return
            fails, warns = preflight.summary(results)
            if fails:
                text = "\n".join("• {}: {}".format(x.title, x.detail) for x in results if x.level == "fail")
                box = QMessageBox(QMessageBox.Icon.Warning, "Check & Build",
                                  "The checks found {} problem(s). Fix them first (double-click a row to open "
                                  "the page that fixes it):\n\n{}".format(fails, text), parent=self)
                box.addButton("Fix first", QMessageBox.ButtonRole.RejectRole)
                anyway = box.addButton("Build anyway", QMessageBox.ButtonRole.DestructiveRole)
                box.exec()
                if box.clickedButton() is not anyway:
                    return
            self._build(then_build)
        self.task("Check the image", lambda t: preflight.run(proj, deep=deep), done)

    def _show_checks(self, results):
        self._results = results
        order = {lvl: i for i, lvl in enumerate(reversed(preflight.LEVELS))}
        results = sorted(results, key=lambda x: order[x.level])
        self._results = results
        fill(self.checks, [(self.MARKS[x.level], x.title, x.detail + ("  (double-click to fix)" if x.page and
                                                                      x.level in ("warn", "fail") else ""))
                           for x in results])
        self.checks.setSortingEnabled(False)
        self.checks.resizeColumnToContents(0)
        self.checks.resizeColumnToContents(1)
        fails, warns = preflight.summary(results)
        self.check_state.setText("{} problem(s), {} warning(s){}".format(
            fails, warns, " — ready to build" if not fails else " — fix the problems before building"))

    def _open_fix(self, row, _col):
        if 0 <= row < len(self._results) and self._results[row].page:
            self.main.go(self._results[row].page)

    def apt_install(self):
        names = self.apt_line.text().split()
        if names:
            from eduka_customizer.core.apt import Packages
            proj = self.project
            self.task("Install " + " ".join(names), lambda t: Packages(proj).install(names),
                      lambda _r: self.apt_line.clear())

    def quick_build(self):
        from eduka_customizer.core.isobuild import quick_build
        proj, opts = self.project, self.options()

        def done(out):
            self.result.setText("ISO image (boot files renewed): <b>{}</b>".format(out))
            self.test_iso.setText(str(out))
        self.task("Rebuild boot files", lambda t: quick_build(proj, opts, t.set_progress, t.set_stage), done)

    def open_output(self):
        opener = shutil.which("xdg-open")
        if opener and self.project:
            subprocess.Popen([opener, str(self.project.output)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test(self):
        iso = self.test_iso.text() or self.project.state.get("last_iso")
        try:
            qemu.start(self.project, iso, firmware=self.firmware.currentData(), memory=self.mem.value(),
                       cpus=self.cpus.value(), disk=self.disk.isChecked())
        except Exception as e:
            QMessageBox.warning(self, "QEMU", str(e))

    def reset_disk(self):
        qemu.reset_disk(self.project)
        self.main.stage_label.setText("Test disk and UEFI variables reset")
