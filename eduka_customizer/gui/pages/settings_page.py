"""Settings, host check (doctor) and the error log."""

import os
import tarfile
import time

from eduka_customizer.qt.widgets import QCheckBox, QLineEdit, QMessageBox, QPlainTextEdit

from eduka_customizer import APP_NAME, VERSION_LABEL
from eduka_customizer.core import doctor
from eduka_customizer.core import log as logmod
from eduka_customizer import qt as qtmod
from eduka_customizer.core.config import reload, settings
from eduka_customizer.gui.widgets import fill, table
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
    ("eduka_desktop", "repo", "Eduka-Desktop repository"),
    ("eduka_desktop", "ref", "Eduka-Desktop branch / tag"),
    ("flatpak", "remote_url", "Flathub remote"),
    ("build", "iso_name", "ISO file name template"),
    ("qemu", "memory", "QEMU memory (MiB)"),
    ("qemu", "cpus", "QEMU CPUs"),
]


class SettingsPage(Page):
    title = "Settings"
    nav_title = "Settings"
    subtitle = "Preferences, the tools DistroForge needs on this computer, and the error log for bug reports."
    icon_names = ("preferences-system", "configure")
    needs_rootfs = False

    def build(self):
        c = self.card("Preferences", "Stored in /etc/distroforge/distroforge.conf. Update the "
                                     "codenames when Debian makes a new release.")
        f = c.form()
        self.edits = {}
        for section, key, text in FIELDS:
            e = QLineEdit()
            self.edits[(section, key)] = e
            f.addRow(text + ":", e)
        self.oldstable = QCheckBox("Allow Debian oldstable (not recommended)")
        f.addRow("", self.oldstable)
        self.free_nav = QCheckBox("Free navigation (expert mode): open every menu at any time instead of "
                                  "one step after the other")
        f.addRow("", self.free_nav)
        self.apply_now = QCheckBox("Apply every change at once (expert mode) instead of collecting the changes in "
                                   "Review & Apply")
        f.addRow("", self.apply_now)
        c.add(label("ISO name fields: {id} {name} {version} {codename} {suite} {debian} {arch} {date}", "muted"))
        c.add(hbox(None, button("Save settings", self.save, "primary")))

        c = self.card("Host computer", "Tools DistroForge uses on this computer.")
        self.host = label("", "muted")
        c.add(self.host)
        self.checks = table(["", "Tool", "Package", "Used for"])
        self.checks.setMinimumHeight(300)
        c.add(self.checks)
        c.add(hbox(button("Check again", self.refresh), None,
                   button("Install missing packages", self.install_missing, "primary")))

        c = self.card("Logs and error reports",
                      "Every run writes a debug log and an error log to /tmp/distroforge/. "
                      "Send them to the developers when something fails.")
        self.log_paths = label("", "muted")
        c.add(self.log_paths)
        self.errors = QPlainTextEdit()
        self.errors.setReadOnly(True)
        self.errors.setMaximumHeight(160)
        c.add(self.errors)
        c.add(hbox(button("Open log folder", self.open_logs), button("Reload", self.load_errors), None,
                   button("Create bug report", self.bug_report, "primary")))

        c.add(hbox(button("About {}, licenses and donations...".format(APP_NAME), lambda: self.main.go("AboutPage")),
                   None))

    def refresh(self):
        cfg = settings()
        for (section, key), e in self.edits.items():
            e.setText(cfg.get(section, key))
        self.oldstable.setChecked(cfg.getbool("debian", "allow_oldstable"))
        self.free_nav.setChecked(cfg.getbool("general", "free_navigation"))
        self.apply_now.setChecked(cfg.get("general", "apply_mode") == "now")
        host = doctor.host_info()
        text = "This computer: {}.".format(host["distro"].summary())
        if not host["supported"]:
            text += " Fine as a build computer; only 'snapshot this computer' needs a Debian-based system."
        text += "  KVM: {}.".format("yes" if host["kvm"] else "no")
        self.host.setText(text)
        rows = [("✓" if r["ok"] else ("✗ required" if r["required"] else "–"), r["item"], r["package"],
                 r["purpose"]) for r in doctor.check()]
        fill(self.checks, rows)
        self.load_errors()

    def load_errors(self):
        self.log_paths.setText("Debug log: {}<br>Error log: {}".format(logmod.DEBUG_LOG, logmod.ERROR_LOG))
        try:
            with open(logmod.ERROR_LOG, encoding="utf-8", errors="replace") as fh:
                text = fh.read()[-20000:]
        except OSError:
            text = ""
        self.errors.setPlainText(text or "No errors recorded.")
        self.errors.verticalScrollBar().setValue(self.errors.verticalScrollBar().maximum())

    def open_logs(self):
        from eduka_customizer.gui.opener import open_url
        open_url(logmod.DEBUG_DIR)

    def bug_report(self):
        """Pack logs and project state into /tmp/distroforge/bug-report-*.tar.gz."""
        name = os.path.join(logmod.DEBUG_DIR, time.strftime("bug-report-%Y%m%d-%H%M%S.tar.gz"))
        with tarfile.open(name, "w:gz") as tf:
            for f in os.listdir(logmod.DEBUG_DIR):
                if f.endswith((".log",)) or ".log." in f:
                    tf.add(os.path.join(logmod.DEBUG_DIR, f), arcname=f)
            p = self.main.project
            if p:
                for extra in (p.state_file, p.logs / "distroforge.log", p.logs / "live-session.log",
                              p.logs / "qemu.log"):
                    if extra.exists():
                        tf.add(str(extra), arcname="project/" + extra.name)
            info = doctor.host_info()
            import io
            data = "DistroForge {}\nHost: {}\nQt: {}\n".format(
                VERSION_LABEL, info["distro"].summary(), qtmod.version())
            ti = tarfile.TarInfo("system.txt")
            ti.size = len(data.encode())
            tf.addfile(ti, io.BytesIO(data.encode()))
        os.chmod(name, 0o644)
        QMessageBox.information(self, "Bug report", "Created:\n{}\n\nAttach this file to your bug "
                                                    "report.".format(name))

    def save(self):
        cfg = settings()
        for (section, key), e in self.edits.items():
            cfg.set(section, key, e.text().strip())
        cfg.set("debian", "allow_oldstable", "yes" if self.oldstable.isChecked() else "no")
        cfg.set("general", "free_navigation", "yes" if self.free_nav.isChecked() else "no")
        cfg.set("general", "apply_mode", "now" if self.apply_now.isChecked() else "review")
        try:
            cfg.save()
        except OSError as e:
            QMessageBox.warning(self, "Settings", "Could not save: {}".format(e))
            return
        reload()
        self.main.update_state()
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
