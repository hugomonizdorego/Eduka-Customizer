"""Kernel page: installed kernels, Debian/backports/third-party kernels, .deb files,
removal, initramfs, GRUB defaults of the installed system, firmware and DKMS."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QFileDialog, QLineEdit, QMessageBox, QPlainTextEdit, QSpinBox,
                                          QTreeWidget, QTreeWidgetItem)

from eduka_customizer.core.kernel import THIRD_PARTY, Kernels
from eduka_customizer.gui.widgets import FilePicker, Page, button, combo, hbox, label


def _size(n):
    return "{:.0f} MiB".format(n / 1024 ** 2) if n else "?"


class KernelPage(Page):
    title = "Kernel"
    nav_title = "Kernel"
    subtitle = ("Step 8 · The Linux kernel of your distribution: Debian kernels, backports or third-party "
                "kernels, firmware and drivers, and the GRUB settings of installed systems. Your changes wait in "
                "Review & Apply (step 14).")
    icon_names = ("preferences-system", "cpu", "applications-system")
    CHANGES = ('Install ', 'Remove kernel', 'Hold ', 'Unhold ', 'Update initramfs', 'Copy kernel', 'update-grub', 'Rebuild DKMS', 'Save GRUB', 'Use ')

    def build(self):
        c = self.card("Installed kernels")
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Version", "Package", "Origin", "Size", "initrd", "Headers", "ISO", "Held"])
        self.tree.setRootIsDecorated(False)
        self.tree.setMinimumHeight(170)
        c.add(self.tree)
        self.meta = label("", "muted")
        c.add(self.meta)
        c.add(hbox(button("Remove", self.remove, "danger"), button("Hold / unhold", self.toggle_hold), None,
                   button("Update initramfs", self.initramfs), button("Copy to the ISO now", self.copy_to_iso),
                   button("Use for the ISO", self.use_for_iso, "primary")))

        c = self.card("Install a Debian kernel", "Debian's kernels are signed for Secure Boot.")
        self.debian = combo([("linux-image-amd64", "linux-image-amd64 (newest of the release, recommended)")],
                            editable=True)
        self.headers = QCheckBox("Also install headers (needed for DKMS drivers such as VirtualBox or NVIDIA)")
        c.add(hbox(self.debian, button("Show all", self.list_debian)))
        c.add(self.headers)
        c.add(hbox(None, button("Install", self.install_debian, "primary")))

        c = self.card("Backports and third-party kernels")
        self.preset = combo([(k, "{} — {}".format(v[0], v[1])) for k, v in THIRD_PARTY.items()])
        c.add(self.preset)
        c.add(label("Third-party kernels are not signed: Secure Boot must be disabled to boot them. Keep "
                    "Debian's kernel installed as a fallback.", "muted"))
        c.add(hbox(None, button("Add repository and install", self.install_preset, "primary")))

        c = self.card("Third-party repository terminal",
                      "Type the commands of the kernel's website here (they run as root inside the image): add "
                      "its repository and key, then 'apt update'. Its kernels appear below. If you install one, "
                      "the repository and the kernel stay in the system; otherwise the repository is only "
                      "temporary and is removed again (at the latest when the ISO is built).")
        self.console_out = QPlainTextEdit()
        self.console_out.setReadOnly(True)
        self.console_out.setObjectName("console")
        self.console_out.setMinimumHeight(170)
        self.console_out.setPlainText("# Example (XanMod):\n"
                                      "# wget -qO - https://dl.xanmod.org/archive.key | gpg --dearmor -o "
                                      "/etc/apt/keyrings/xanmod.gpg\n"
                                      "# echo 'deb [signed-by=/etc/apt/keyrings/xanmod.gpg] "
                                      "http://deb.xanmod.org releases main' > /etc/apt/sources.list.d/xanmod.list\n"
                                      "# apt update\n")
        c.add(self.console_out)
        self.console_in = QLineEdit()
        self.console_in.setObjectName("consoleInput")
        self.console_in.setPlaceholderText("root@image:~# type a command and press Enter")
        self.console_in.returnPressed.connect(self.run_console)
        self._history, self._hpos = [], 0
        c.add(hbox(self.console_in, button("Run", self.run_console), button("apt update", self.console_update)))
        self.temp_tree = QTreeWidget()
        self.temp_tree.setHeaderLabels(["Kernel package", "Version", "Repository"])
        self.temp_tree.setRootIsDecorated(False)
        self.temp_tree.setMinimumHeight(120)
        c.add(self.temp_tree)
        self.temp_state = label("", "muted")
        c.add(self.temp_state)
        c.add(hbox(button("Keep or remove the temporary repositories now", self.finalize_repos), None,
                   button("Install selected kernel", self.install_temp_kernel, "primary")))

        c = self.card("Kernel from your own repository or from files")
        f = c.form()
        self.r_name = QLineEdit()
        self.r_name.setPlaceholderText("short name, e.g. mykernel")
        self.r_uri = QLineEdit()
        self.r_uri.setPlaceholderText("https://example.org/debian")
        self.r_suite = QLineEdit()
        self.r_suite.setPlaceholderText("e.g. trixie or stable")
        self.r_comp = QLineEdit("main")
        self.r_key = FilePicker("Repository key", "Keys (*.gpg *.asc *.key);;All files (*)")
        self.r_pkgs = QLineEdit()
        self.r_pkgs.setPlaceholderText("package names, e.g. linux-image-custom linux-headers-custom")
        for text, w in (("Name:", self.r_name), ("URI:", self.r_uri), ("Suite:", self.r_suite),
                        ("Components:", self.r_comp), ("Key (file or URL):", self.r_key),
                        ("Packages:", self.r_pkgs)):
            f.addRow(text, w)
        c.add(hbox(button("Install .deb files...", self.install_debs), None,
                   button("Add repository and install", self.install_repo, "primary")))

        c = self.card("GRUB of the installed system",
                      "Written to /etc/default/grub.d/95-eduka-customizer.cfg and used when Calamares "
                      "installs GRUB (and by every later update-grub).")
        f = c.form()
        self.g_timeout = QSpinBox()
        self.g_timeout.setRange(-1, 120)
        self.g_timeout.setSuffix(" s")
        f.addRow("Timeout:", self.g_timeout)
        self.g_style = combo([("menu", "Show the menu"), ("countdown", "Countdown"), ("hidden", "Hidden (Shift/Esc shows it)")])
        f.addRow("Menu:", self.g_style)
        self.g_default = combo([("0", "First entry"), ("saved", "Last chosen entry")])
        f.addRow("Default entry:", self.g_default)
        self.g_cmdline = QLineEdit()
        f.addRow("Kernel options:", self.g_cmdline)
        self.g_osprober = QCheckBox("Find other systems (Windows, other Linux) for the menu (os-prober)")
        f.addRow("", self.g_osprober)
        self.g_recovery = QCheckBox("Hide recovery entries")
        f.addRow("", self.g_recovery)
        self.g_gfx = combo(["", "auto", "1024x768", "1280x800", "1920x1080"], editable=True)
        f.addRow("Resolution:", self.g_gfx)
        c.add(hbox(button("Run update-grub", self.update_grub), None,
                   button("Save GRUB settings", self.save_grub, "primary")))

        c = self.card("Drivers")
        c.add(label("Firmware makes Wi-Fi, graphics and sound work on most laptops (needs the non-free-firmware "
                    "component). DKMS rebuilds extra drivers for every installed kernel.", "muted"))
        c.add(hbox(button("Install common firmware", self.firmware, "primary"),
                   button("Rebuild DKMS drivers", self.dkms), None))

    # Helpers -------------------------------------------------------------------------
    def k(self):
        return Kernels(self.project)

    def _selected(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.ItemDataRole.UserRole) if it else None

    def refresh(self):
        if not self.project:
            return
        self.show_temp_repos()
        k = self.k()
        kernels, meta = k.installed()
        self._kernels = {x["version"]: x for x in kernels}
        keep = self._selected()
        self.tree.clear()
        for x in kernels:
            it = QTreeWidgetItem([x["version"], x["package"] or "-", x["origin"], _size(x["size"]),
                                  "yes" if x["initrd"] else "missing", "yes" if x["headers"] else "",
                                  "●" if x["iso"] else "", "held" if x["held"] else ""])
            it.setData(0, Qt.ItemDataRole.UserRole, x["version"])
            self.tree.addTopLevelItem(it)
            if x["version"] == keep:
                self.tree.setCurrentItem(it)
        for i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(i)
        self.meta.setText("Kept up to date by: " + ", ".join(
            "{}{}".format(m["package"], " (held)" if m["held"] else "") for m in meta) if meta
            else "No kernel metapackage: kernels are not updated automatically.")
        g = k.grub_defaults()
        try:
            self.g_timeout.setValue(int(g.get("GRUB_TIMEOUT", "5")))
        except ValueError:
            self.g_timeout.setValue(5)
        self.g_style.setCurrentIndex(max(0, self.g_style.findData(g.get("GRUB_TIMEOUT_STYLE", "menu"))))
        self.g_default.setCurrentIndex(max(0, self.g_default.findData(g.get("GRUB_DEFAULT", "0"))))
        self.g_cmdline.setText(g.get("GRUB_CMDLINE_LINUX_DEFAULT", "quiet splash"))
        self.g_osprober.setChecked(g.get("GRUB_DISABLE_OS_PROBER", "true") == "false")
        self.g_recovery.setChecked(g.get("GRUB_DISABLE_RECOVERY", "false") == "true")
        self.g_gfx.setCurrentText(g.get("GRUB_GFXMODE", ""))

    def _run(self, name, func):
        self.task(name, func, lambda _r: (self.refresh(), self.main.update_state()))

    # Actions ----------------------------------------------------------------------------
    def remove(self):
        v = self._selected()
        if not v:
            return
        if QMessageBox.question(self, "Remove kernel", "Remove kernel {} from the image?".format(v)) != \
                QMessageBox.StandardButton.Yes:
            return
        proj = self.project
        self._run("Remove kernel " + v, lambda t: Kernels(proj).remove(v))

    def toggle_hold(self):
        v = self._selected()
        x = self._kernels.get(v) if v else None
        if not x or not x["package"]:
            return
        proj, pkg, on = self.project, x["package"], not x["held"]
        self._run(("Hold " if on else "Unhold ") + pkg, lambda t: Kernels(proj).hold(pkg, on))

    def initramfs(self):
        v = self._selected()
        proj = self.project
        self._run("Update initramfs", lambda t: Kernels(proj).update_initramfs(v))

    def use_for_iso(self):
        v = self._selected()
        if v:
            self.k().use_for_iso(v)
            self.refresh()
            self.main.stage_label.setText("The ISO will boot kernel " + v)

    def copy_to_iso(self):
        v = self._selected()
        proj = self.project
        self._run("Copy kernel to the ISO", lambda t: Kernels(proj).copy_to_iso(v))

    def list_debian(self):
        proj = self.project

        def done(rows):
            keep = self.debian.currentText()
            self.debian.clear()
            for name, desc in rows:
                self.debian.addItem("{} — {}".format(name, desc), name)
            idx = self.debian.findData("linux-image-amd64")
            self.debian.setCurrentIndex(idx if idx >= 0 else 0)
            if not rows:
                self.debian.setEditText(keep)
        self.task("List Debian kernels", lambda t: Kernels(proj).available(), done)

    def install_debian(self):
        data = self.debian.currentData()
        words = self.debian.currentText().split()
        name = data if data and self.debian.currentText().startswith(data) else (words[0] if words else "")
        if not name:
            QMessageBox.information(self, "Kernel", "Choose or type a kernel package first.")
            return
        proj, headers = self.project, self.headers.isChecked()
        self._run("Install kernel " + name, lambda t: Kernels(proj).install([name], headers=headers))

    def install_preset(self):
        key = self.preset.currentData()
        proj, headers = self.project, self.headers.isChecked()
        self._run("Install " + THIRD_PARTY[key][0], lambda t: Kernels(proj).install_third_party(key, headers))

    def install_repo(self):
        name, uri, suite = self.r_name.text().strip(), self.r_uri.text().strip(), self.r_suite.text().strip()
        pkgs = self.r_pkgs.text().split()
        if not (name and uri and suite and pkgs):
            QMessageBox.information(self, "Kernel", "Name, URI, suite and packages are needed.")
            return
        proj, comp, key = self.project, self.r_comp.text().strip(), self.r_key.text()
        self._run("Install kernel from " + name,
                  lambda t: Kernels(proj).add_repository(name, uri, suite, comp, key, pkgs))

    # Third-party repository terminal --------------------------------------------------
    def run_console(self, command=None):
        cmd = command if isinstance(command, str) else self.console_in.text().strip()
        if not cmd:
            return
        self._history.append(cmd)
        self.console_in.clear()
        self.console_out.appendPlainText("root@image:~# " + cmd)
        proj = self.project

        def done(out):
            self.console_out.appendPlainText((out or "").rstrip())
            self.show_temp_repos()
        self.task("Terminal: " + cmd[:60], lambda t: Kernels(proj).console(cmd), done)

    def console_update(self):
        self.run_console("apt-get update")

    def show_temp_repos(self):
        self.temp_tree.clear()
        repos = self.k().temp_repos()
        for repo in repos:
            for name, versions in sorted(repo["kernels"].items()):
                it = QTreeWidgetItem([name, ", ".join(sorted(set(versions))), " ".join(repo["uris"])])
                it.setData(0, Qt.ItemDataRole.UserRole, name)
                self.temp_tree.addTopLevelItem(it)
        for i in range(3):
            self.temp_tree.resizeColumnToContents(i)
        files = self.k().temp_files()
        self.temp_state.setText("Temporary repository files: {}".format(", ".join(files)) if files else
                                "No temporary repository.")

    def install_temp_kernel(self):
        it = self.temp_tree.currentItem()
        if not it:
            QMessageBox.information(self, "Kernel", "Select a kernel of the new repository first.")
            return
        name = it.data(0, Qt.ItemDataRole.UserRole)
        proj, headers = self.project, self.headers.isChecked()

        def work(t):
            k = Kernels(proj)
            k.install([name], headers=headers)
            return k.finalize_temp_repos()
        self.task("Install " + name, work, lambda r: (self.show_temp_repos(), self._report_repos(r)))

    def finalize_repos(self):
        proj = self.project
        self.task("Temporary repositories", lambda t: Kernels(proj).finalize_temp_repos(),
                  lambda r: (self.show_temp_repos(), self._report_repos(r)))

    def _report_repos(self, result):
        kept, removed = result or ([], [])
        QMessageBox.information(self, "Repositories", "Kept (a kernel was installed from them): {}\n\n"
                                "Removed (temporary): {}".format(", ".join(kept) or "none",
                                                                 ", ".join(removed) or "none"))

    def install_debs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Kernel packages", "", "Debian packages (*.deb)")
        if files:
            proj = self.project
            self._run("Install kernel packages", lambda t: Kernels(proj).install_debs(files))

    def save_grub(self):
        values = {"GRUB_TIMEOUT": str(self.g_timeout.value()), "GRUB_TIMEOUT_STYLE": self.g_style.currentData(),
                  "GRUB_DEFAULT": self.g_default.currentData(),
                  "GRUB_CMDLINE_LINUX_DEFAULT": self.g_cmdline.text().strip(),
                  "GRUB_DISABLE_OS_PROBER": "false" if self.g_osprober.isChecked() else "true",
                  "GRUB_DISABLE_RECOVERY": "true" if self.g_recovery.isChecked() else "false",
                  "GRUB_GFXMODE": self.g_gfx.currentText().strip()}
        if values["GRUB_DEFAULT"] == "saved":
            values["GRUB_SAVEDEFAULT"] = "true"
        try:
            self.k().set_grub_defaults(values)
        except ValueError as e:
            QMessageBox.warning(self, "GRUB", str(e))
            return
        self.main.stage_label.setText("GRUB settings saved")

    def update_grub(self):
        proj = self.project

        def done(ran):
            if not ran:
                QMessageBox.information(self, "update-grub", "The image has no installed GRUB menu (normal for "
                                        "a live image). The installer creates it with these settings.")
        self.task("update-grub", lambda t: Kernels(proj).update_grub(), done)

    def firmware(self):
        proj = self.project
        self._run("Install firmware", lambda t: Kernels(proj).install_firmware())

    def dkms(self):
        proj = self.project
        self._run("Rebuild DKMS drivers", lambda t: Kernels(proj).dkms())
