"""Settings, host check (doctor) and About."""

from PyQt6.QtWidgets import QCheckBox, QLineEdit, QMessageBox

from eduka_customizer import APP_NAME, HOMEPAGE, VERSION_LABEL
from eduka_customizer.core import doctor
from eduka_customizer.core.config import reload, settings
from eduka_customizer.gui.pages.packages import fill, table
from eduka_customizer.gui.widgets import Page, button, hbox, label

FIELDS = [
    ("general", "projects_dir", "Projects folder"),
    ("general", "terminal", "Terminal program (empty = automatic)"),
    ("debian", "stable", "Debian stable codename"),
    ("debian", "testing", "Debian testing codename"),
    ("debian", "oldstable", "Debian oldstable codename"),
    ("debian", "mirror", "Debian mirror"),
    ("debian", "security_mirror", "Security mirror"),
    ("debian", "components", "Components"),
    ("edukasaun", "eduka_desktop_repo", "Eduka-Desktop repository"),
    ("edukasaun", "eduka_desktop_ref", "Eduka-Desktop branch / tag"),
    ("flatpak", "remote_url", "Flathub remote"),
    ("build", "iso_name", "ISO file name template"),
    ("qemu", "memory", "QEMU memory (MiB)"),
    ("qemu", "cpus", "QEMU CPUs"),
]


class SettingsPage(Page):
    title = "Settings"
    subtitle = "Global preferences, host computer check and information about Eduka-Customizer."
    icon_names = ("preferences-system", "configure")
    needs_rootfs = False

    def build(self):
        c = self.card("Preferences", "Stored in /etc/eduka-customizer/eduka-customizer.conf. Update the "
                                     "codenames when Debian makes a new release.")
        f = c.form()
        self.edits = {}
        for section, key, text in FIELDS:
            e = QLineEdit()
            self.edits[(section, key)] = e
            f.addRow(text + ":", e)
        self.oldstable = QCheckBox("Allow Debian oldstable (not recommended)")
        f.addRow("", self.oldstable)
        c.add(label("ISO name fields: {id} {name} {version} {codename} {suite} {debian} {arch} {date}", "muted"))
        c.add(hbox(None, button("Save settings", self.save, "primary")))

        c = self.card("Host computer", "Tools Eduka-Customizer uses on this computer.")
        self.host = label("", "muted")
        c.add(self.host)
        self.checks = table(["", "Tool", "Package", "Used for"])
        self.checks.setMinimumHeight(300)
        c.add(self.checks)
        c.add(hbox(button("Check again", self.refresh), None,
                   button("Install missing packages", self.install_missing, "primary")))

        c = self.card("About")
        c.add(label(
            "<b>{} {}</b> — the ISO builder and customizer for <b>Edukasaun OS</b>, based on Debian "
            "stable, testing and sid.<br><br>"
            "Rewritten from <i>Customizer</i> by Ivailo Monev, Mubiin Kimura, Graham Cantin and "
            "contributors. Techniques inspired by <i>Cubic</i> (boot replay, ISO remastering), "
            "<i>remastersys</i> (system snapshot, clean-up) and <i>penguins-eggs</i> (hybrid "
            "BIOS/UEFI boot, exclusion lists).<br><br>"
            "Desktop: <i>Eduka-Desktop</i> — github.com/hugomonizdorego/Eduka-Desktop<br>"
            "Apps: <i>Flathub</i> — flathub.org<br><br>"
            "License: GNU GPL version 3 or later. {}".format(APP_NAME, VERSION_LABEL, HOMEPAGE)))

    def refresh(self):
        cfg = settings()
        for (section, key), e in self.edits.items():
            e.setText(cfg.get(section, key))
        self.oldstable.setChecked(cfg.getbool("debian", "allow_oldstable"))
        host = doctor.host_info()
        text = "This computer: {}.".format(host["distro"].summary())
        if not host["supported"]:
            text += " Note: Eduka-Customizer is meant to run on Debian or Edukasaun OS."
        text += "  KVM: {}.".format("yes" if host["kvm"] else "no")
        self.host.setText(text)
        rows = [("✓" if r["ok"] else ("✗ required" if r["required"] else "–"), r["item"], r["package"],
                 r["purpose"]) for r in doctor.check()]
        fill(self.checks, rows)

    def save(self):
        cfg = settings()
        for (section, key), e in self.edits.items():
            cfg.set(section, key, e.text().strip())
        cfg.set("debian", "allow_oldstable", "yes" if self.oldstable.isChecked() else "no")
        try:
            cfg.save()
        except OSError as e:
            QMessageBox.warning(self, "Settings", "Could not save: {}".format(e))
            return
        reload()
        self.main.stage_label.setText("Settings saved")

    def install_missing(self):
        pkgs = doctor.missing_packages()
        if not pkgs:
            QMessageBox.information(self, "Host computer", "Everything is installed.")
            return
        if QMessageBox.question(self, "Install", "Install on this computer:\n" + " ".join(pkgs)) != \
                QMessageBox.StandardButton.Yes:
            return
        self.task("Install host tools", lambda t: doctor.install_missing(pkgs))
