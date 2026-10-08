"""Init System page: systemd or an alternative (SysVinit, OpenRC, runit)."""

from eduka_customizer.qt.widgets import QMessageBox

from eduka_customizer.core import initsystem
from eduka_customizer.gui.widgets import Page, button, fill, hbox, label, table


class InitSystemPage(Page):
    title = "Init System"
    nav_title = "Init System"
    subtitle = ("Step 8 · The first program the kernel starts, which then starts everything else. Debian uses "
                "systemd; Devuan and its derivatives use SysVinit, OpenRC or runit. Every choice works with the "
                "kernel, live-boot, the boot loaders and the Calamares installer. Your change waits in Review & "
                "Apply (step 12).")
    icon_names = ("preferences-system-services", "system-run")
    CHANGES = ("Use init system",)

    def build(self):
        c = self.card("Init systems", "Select one to read about it.")
        self.list = table(["Init system", "In use", "Description"])
        self.list.setMinimumHeight(230)
        self.list.itemSelectionChanged.connect(self._selected)
        c.add(self.list)
        self.about = label("", "muted")
        c.add(self.about)
        self.use_btn = button("Use this init system", self.use, "primary")
        c.add(hbox(None, self.use_btn))
        c = self.card("What changes with it",
                      "Switching installs the init system and removes the old one (APT), installs elogind so "
                      "desktops keep their login sessions, the matching live-config backend, init scripts that "
                      "Debian dropped (orphan-sysvinit-scripts), and init scripts for the services DistroForge "
                      "adds (boot sounds, Flatpak on first boot). The installer gets the matching services "
                      "module and does not run systemd-only steps. GNOME needs systemd.")
        self.state = label("", "muted")
        c.add(self.state)
        self._rows = []

    def refresh(self):
        if not self.project:
            return
        self._rows = initsystem.options(self.project)
        self.list.blockSignals(True)
        fill(self.list, [(name, "✔ in use" if cur else ("not available" if not ok else ""), desc.split(".")[0])
                         for _i, name, desc, ok, _w, cur in self._rows], sort=False)
        self.list.resizeColumnToContents(0)
        self.list.blockSignals(False)
        cur = next((i for i, r in enumerate(self._rows) if r[5]), 0)
        self.list.selectRow(cur)
        self._selected()
        d = self.project.distro
        lines = ["{} {}".format({"ok": "✔", "warn": "⚠", "fail": "✘"}[lvl], text)
                 for lvl, text in initsystem.check(self.project)]
        if d.is_devuan:
            lines.append("Devuan {}: without systemd by design.".format(d.devuan_codename or ""))
        self.state.setText("<br>".join(lines))

    def _row(self):
        rows = sorted({i.row() for i in self.list.selectedIndexes()})
        return self._rows[rows[0]] if rows and rows[0] < len(self._rows) else None

    def _selected(self):
        r = self._row()
        if not r:
            return
        iid, name, desc, ok, why, cur = r
        self.about.setText("<b>{}</b> — {}".format(name, desc if ok else "not available: " + why))
        self.use_btn.setEnabled(ok and not cur)
        self.use_btn.setText("In use" if cur else "Use {}".format(name))

    def use(self):
        r = self._row()
        if not r:
            return
        iid, name = r[0], r[1]
        if QMessageBox.question(self, "Init system", "Switch the image to {}? Packages are installed and "
                                "removed; you can switch back the same way.".format(name)) \
                != QMessageBox.StandardButton.Yes:
            return
        proj = self.project
        self.task("Use init system " + name, lambda t: initsystem.use(proj, iid), lambda _r: self.refresh())
