"""Packages page: every Debian package of the image's sources with tick boxes and a
fast search, removal of default applications, and the other ways to install."""

from eduka_customizer.qt.widgets import QCheckBox, QFileDialog, QLineEdit, QMessageBox

from eduka_customizer.core.apt import Packages, read_package_list
from eduka_customizer.gui.package_browser import AppRemover, PackageBrowser
from eduka_customizer.gui.widgets import Page, button, hbox


class PackagesPage(Page):
    title = "Packages and Applications"
    nav_title = "Packages"
    subtitle = ("Every package of the Debian sources of the image: search, tick to install, untick to "
                "remove. Or remove the applications that came with the ISO. Changes go straight into "
                "the image.")
    icon_names = ("system-software-install", "package-x-generic")

    def build(self):
        c = self.card("Maintenance")
        c.add(hbox(button("Refresh package lists", self.update_lists, "primary",
                          tooltip="apt update inside the image (needs internet)"),
                   button("Upgrade all", self.upgrade), button("Autoremove", self.autoremove),
                   button("Install .deb files...", self.install_debs), None,
                   button("Synaptic / terminal / live desktop...", lambda: self.main.go("TerminalPage"))))

        c = self.card("All Debian packages",
                      "Ticked = installed in the ISO. Green: installed or to be installed; red: to be removed. "
                      "'Applications' hides libraries and other parts nobody starts from the menu.")
        self.browser = PackageBrowser()
        c.add(self.browser)
        self.no_rec = QCheckBox("Do not install recommended packages (smaller image)")
        self.names = QLineEdit()
        self.names.setPlaceholderText("or type package names: vlc gimp ...")
        self.names.returnPressed.connect(self.tick_names)
        c.add(hbox(self.names, button("Tick", self.tick_names)))
        c.add(hbox(self.no_rec, None, button("Import list...", self.import_list),
                   button("Export list...", self.export_list), button("Reset", self.browser.reset),
                   button("Apply changes", self.apply, "primary")))

        c = self.card("Remove applications of the ISO",
                      "Applications that came with the source ISO (they have a menu entry). Tick the ones "
                      "your distribution should not have; the parts nothing else needs are removed with them.")
        self.remover = AppRemover()
        c.add(self.remover)
        c.add(hbox(None, button("Remove ticked applications", self.remove_apps, "danger")))
        self._loaded_for = None

    def _stamp(self):
        """Changes when packages were installed or the lists refreshed (also by other pages)."""
        r = self.project.rootfs
        out = [str(self.project.path)]
        for p in (r / "var/lib/dpkg/status", r / "var/lib/apt/lists"):
            out.append(p.stat().st_mtime if p.exists() else 0)
        return tuple(out)

    def refresh(self):
        if self.project and self._loaded_for != self._stamp():
            self.reload()

    def project_changed(self):
        self._loaded_for = None

    def reload(self):
        self.browser.load(self.project.rootfs)
        self.remover.load(self.project.rootfs)
        self._loaded_for = self._stamp()

    # Actions ---------------------------------------------------------------------
    def tick_names(self):
        self.browser.select(self.names.text().split())
        self.names.clear()

    def apply(self):
        inst, rem = self.browser.changes()
        if not inst and not rem:
            QMessageBox.information(self, "Packages", "Nothing to change: tick or untick packages first.")
            return
        msg = []
        if inst:
            msg.append("Install: " + " ".join(inst))
        if rem:
            msg.append("Remove: " + " ".join(rem))
        if QMessageBox.question(self, "Apply changes", "\n\n".join(msg)) != QMessageBox.StandardButton.Yes:
            return
        proj, no_rec = self.project, self.no_rec.isChecked()

        def work(t):
            pk = Packages(proj)
            with pk.chroot:
                if rem:
                    t.set_stage("Removing packages")
                    pk.remove(rem)
                if inst:
                    t.set_stage("Installing packages")
                    pk.install(inst, no_recommends=no_rec)
        self.task("Apply package changes", work, lambda _r: self.reload())

    def remove_apps(self):
        names = self.remover.selected()
        if not names:
            return
        if QMessageBox.question(self, "Remove applications", "Remove from the image:\n\n" + " ".join(names)) != \
                QMessageBox.StandardButton.Yes:
            return
        proj = self.project
        self.task("Remove applications", lambda t: Packages(proj).remove(names), lambda _r: self.reload())

    def update_lists(self):
        proj = self.project
        self.task("Refresh package lists", lambda t: Packages(proj).update(), lambda _r: self.reload())

    def upgrade(self):
        proj = self.project
        self.task("Upgrade all packages", lambda t: Packages(proj).upgrade(), lambda _r: self.reload())

    def autoremove(self):
        proj = self.project

        def work(t):
            pk = Packages(proj)
            with pk.chroot:
                pk.autoremove()
        self.task("Autoremove", work, lambda _r: self.reload())

    def install_debs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Install .deb packages", "", "Debian packages (*.deb)")
        if files:
            proj = self.project
            self.task("Install .deb files", lambda t: Packages(proj).install_debs(files), lambda _r: self.reload())

    def import_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import package list", "", "Text files (*.txt *.list);;All (*)")
        if path:
            inst, rem = read_package_list(path)
            self.browser.select(inst)
            self.browser.model.checked -= set(rem)
            self.browser._apply_filter()

    def export_list(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export package list", "packages.txt", "Text files (*.txt)")
        if path:
            inst, rem = self.browser.changes()
            lines = ["# Eduka-Customizer package list. '-name' means remove."] + inst + ["-" + n for n in rem]
            with open(path, "w") as fh:
                fh.write("\n".join(lines) + "\n")

