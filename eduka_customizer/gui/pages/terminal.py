"""Terminal & Live page: live edit session, chroot terminal, hooks, files."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from eduka_customizer.qt.core import Qt, QTimer
from eduka_customizer.qt.gui import QFont
from eduka_customizer.qt.widgets import (QFileDialog, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
                             QSplitter)

from eduka_customizer.core import bootloader, hooks
from eduka_customizer.core.chroot import Chroot, mounts_under
from eduka_customizer.core.config import settings
from eduka_customizer.core.desktop import sessions
from eduka_customizer.core.livesession import MODES, LiveSession
from eduka_customizer.gui.widgets import Page, button, combo, hbox, label

# terminal -> arguments placed before the command
TERMINALS = [("x-terminal-emulator", ["-e"]), ("qterminal", ["-e"]), ("konsole", ["-e"]),
             ("xfce4-terminal", ["-x"]), ("gnome-terminal", ["--"]), ("mate-terminal", ["-x"]),
             ("lxterminal", ["-e"]), ("tilix", ["-e"]), ("xterm", ["-e"])]


def terminal_command(cmd):
    preferred = settings().get("general", "terminal")
    for name, args in ([(preferred, ["-e"])] if preferred else []) + TERMINALS:
        exe = shutil.which(name)
        if exe:
            if name in ("qterminal",):
                import shlex
                return [exe] + args + [" ".join(shlex.quote(c) for c in cmd)]
            return [exe] + args + cmd
    return None


SETTINGS_APPS = [
    ("eduka-menu-settings", "Eduka-Menu and Eduka-Panel settings"),
    ("lxqt-config-appearance", "LXQt appearance (themes, icons, fonts)"),
    ("lxqt-config", "LXQt configuration center"),
    ("pcmanfm-qt --desktop-pref", "Desktop: wallpaper and desktop icons"),
    ("obconf", "Openbox window manager"),
    ("xfce4-appearance-settings", "Xfce appearance"),
    ("xfce4-settings-manager", "Xfce settings manager"),
    ("systemsettings", "KDE System Settings"),
    ("gnome-control-center", "GNOME Settings"),
    ("gnome-tweaks", "GNOME Tweaks"),
    ("mate-control-center", "MATE Control Center"),
    ("cinnamon-settings", "Cinnamon System Settings"),
    ("lxappearance", "LXAppearance (GTK themes)"),
    ("qt5ct", "Qt5 settings"),
    ("qt6ct", "Qt6 settings"),
    ("lightdm-gtk-greeter-settings", "LightDM GTK greeter settings"),
    ("xfce4-terminal", "Terminal (Xfce)"),
    ("qterminal", "Terminal (QTerminal)"),
]


class TerminalPage(Page):
    title = "Terminal & Live"
    subtitle = ("Work inside the image directly: start its desktop in a window and change "
                "settings live, open a root terminal, run scripts or edit files. Every change is "
                "saved into the image and ends up in the next ISO.")
    icon_names = ("utilities-terminal", "terminal")

    def build(self):
        c = self.card("Live edit session",
                      "Runs the image's desktop in a nested window (Xephyr). In the default mode "
                      "your changes become the defaults of every new user (/etc/skel).")
        f = c.form()
        self.session = combo([])
        f.addRow("Session:", self.session)
        self.resolution = combo(["1024x768", "1280x800", "1366x768", "1600x900", "1920x1080"], "1280x800",
                                editable=True)
        f.addRow("Window size:", self.resolution)
        self.mode = combo(list(MODES.items()))
        f.addRow("Mode:", self.mode)
        self.live_state = label("Not running", "muted")
        f.addRow("Status:", self.live_state)
        self.app_cmd = QLineEdit()
        self.app_cmd.setPlaceholderText("e.g. lxqt-config-appearance, eduka-menu-settings, pcmanfm-qt")
        c.add(hbox(button("Start live session", self.start_live, "primary"),
                   button("Stop", self.stop_live, "danger"), None, self.app_cmd,
                   button("Run in session", self.run_app)))
        self.apps = combo([])
        c.add(hbox(label("Settings app"), self.apps, button("Open in session", self.run_settings_app), None,
                   button("Stop and build ISO", self.stop_and_build)))
        self.poll = QTimer(self)
        self.poll.timeout.connect(self._poll_live)

        c = self.card("Terminal", "A root shell inside the image (apt, nano, systemctl enable ...).")
        self.cmd = QLineEdit()
        self.cmd.setPlaceholderText("Run one command inside the image, e.g. apt-get install -y vlc")
        self.cmd.returnPressed.connect(self.run_command)
        c.add(hbox(self.cmd, button("Run", self.run_command)))
        c.add(hbox(button("Open terminal in the image", self.open_terminal, "primary",
                          ("utilities-terminal",)),
                   button("Open root filesystem folder", lambda: self.open_folder(self.project.rootfs)),
                   button("Open ISO folder", lambda: self.open_folder(self.project.isodir)), None,
                   button("Unmount everything", self.unmount)))
        self.mounts = label("", "muted")
        c.add(self.mounts)

        c = self.card("Hooks", "Shell scripts run as root inside the image, in name order "
                               "(stored in <project>/hooks).")
        self.hooks = QListWidget()
        self.hooks.setMaximumHeight(130)
        c.add(self.hooks)
        c.add(hbox(button("Add script...", self.add_hook), button("Remove", self.remove_hook, "danger"),
                   None, button("Run selected", self.run_selected_hook),
                   button("Run all", self.run_all_hooks, "primary")))

        c = self.card("Boot files of the ISO", "Edit GRUB and ISOLINUX configuration directly.")
        split = QSplitter()
        self.boot_files = QListWidget()
        self.boot_files.setMinimumWidth(220)
        self.boot_files.currentTextChanged.connect(self.load_boot_file)
        self.boot_edit = QPlainTextEdit()
        self.boot_edit.setFont(QFont("monospace"))
        self.boot_edit.setMinimumHeight(240)
        split.addWidget(self.boot_files)
        split.addWidget(self.boot_edit)
        split.setStretchFactor(1, 3)
        c.add(split)
        c.add(hbox(None, button("Save boot file", self.save_boot_file, "primary")))

    def refresh(self):
        if not self.project:
            return
        cur = self.session.currentData()
        self.session.clear()
        for s in sessions(self.project.rootfs):
            if s["type"] == "x11":
                self.session.addItem(s["name"], s["id"])
        want = cur or self.project.state.get("desktop", {}).get("session")
        if want and self.session.findData(want) >= 0:
            self.session.setCurrentIndex(self.session.findData(want))
        self.apps.clear()
        for cmd, text in SETTINGS_APPS:
            exe = cmd.split()[0]
            if any((self.project.rootfs / d / exe).exists() for d in ("usr/bin", "usr/sbin", "usr/games")):
                self.apps.addItem(text, cmd)
        self.hooks.clear()
        for h in hooks.hook_dirs(self.project):
            self.hooks.addItem(h.name)
        current = self.boot_files.currentItem().text() if self.boot_files.currentItem() else ""
        self.boot_files.blockSignals(True)
        self.boot_files.clear()
        for f in bootloader.config_files(self.project.isodir):
            self.boot_files.addItem(str(f.relative_to(self.project.isodir)))
        self.boot_files.blockSignals(False)
        if current:
            items = self.boot_files.findItems(current, Qt.MatchFlag.MatchExactly)
            if items:
                self.boot_files.setCurrentItem(items[0])
        n = len(mounts_under(self.project.rootfs))
        self.mounts.setText("{} filesystems mounted inside the image".format(n) if n else
                            "Nothing is mounted inside the image.")
        self._poll_live()

    # Live session ------------------------------------------------------------------
    def start_live(self):
        if self.main.task:
            QMessageBox.information(self, "Live session", "Wait for the running task to finish.")
            return
        if self.main.live and self.main.live.running:
            return
        live = LiveSession(self.project)
        try:
            display = live.start(self.session.currentData(), self.resolution.currentText(),
                                 self.mode.currentData())
        except Exception as e:
            QMessageBox.warning(self, "Live session", str(e))
            return
        self.main.live = live
        self.live_state.setText("Running on display :{} - close the window or press Stop".format(display))
        self.poll.start(1500)

    def _poll_live(self):
        live = self.main.live
        if live and not live.running:
            live.stop()
            self.main.live = None
            self.poll.stop()
            self.live_state.setText("Stopped. Changes were saved into the image.")
            self.main.update_state()
        elif not live:
            self.poll.stop()

    def stop_live(self):
        if self.main.live:
            self.main.live.stop()
            self.main.live = None
            self.live_state.setText("Stopped. Changes were saved into the image.")
            self.main.update_state()

    def stop_and_build(self):
        self.stop_live()
        self.main.go("BuildPage")

    def run_app(self):
        cmd = self.app_cmd.text().strip()
        if cmd and self.main.live:
            try:
                self.main.live.run_app(cmd)
            except RuntimeError as e:
                QMessageBox.warning(self, "Live session", str(e))

    def run_settings_app(self):
        cmd = self.apps.currentData()
        if not cmd:
            return
        if not (self.main.live and self.main.live.running):
            QMessageBox.information(self, "Live session", "Start the live session first.")
            return
        self.main.live.run_app(cmd)

    # Terminal -------------------------------------------------------------------------
    def run_command(self):
        command = self.cmd.text().strip()
        if command:
            proj = self.project
            self.task("Run command", lambda t: hooks.run_command(proj, command))

    def open_terminal(self):
        pkg_root = str(Path(__file__).resolve().parents[3])
        inner = ["env", "PYTHONPATH=" + pkg_root, sys.executable, "-m", "eduka_customizer",
                 "-p", str(self.project.path), "shell"]
        cmd = terminal_command(inner)
        if not cmd:
            QMessageBox.warning(self, "Terminal", "No terminal emulator found. Install qterminal or xterm.")
            return
        subprocess.Popen(cmd, start_new_session=True)

    def open_folder(self, path):
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(path)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def unmount(self):
        if self.main.live and self.main.live.running:
            QMessageBox.information(self, "Unmount", "Stop the live session first.")
            return
        if self.main.task:
            QMessageBox.information(self, "Unmount", "Wait for the running task to finish.")
            return
        Chroot(self.project.rootfs).force_release()
        self.refresh()
        self.main.update_state()

    # Hooks ---------------------------------------------------------------------------
    def add_hook(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add hook scripts", "", "Scripts (*.sh *);;All (*)")
        d = self.project.path / "hooks"
        d.mkdir(exist_ok=True)
        for f in files:
            shutil.copy2(f, d / Path(f).name)
            os.chmod(d / Path(f).name, 0o755)
        self.refresh()

    def remove_hook(self):
        it = self.hooks.currentItem()
        if it and QMessageBox.question(self, "Remove hook", "Remove {}?".format(it.text())) == \
                QMessageBox.StandardButton.Yes:
            (self.project.path / "hooks" / it.text()).unlink(missing_ok=True)
            self.refresh()

    def run_selected_hook(self):
        it = self.hooks.currentItem()
        if it:
            proj, path = self.project, self.project.path / "hooks" / it.text()
            self.task("Run hook " + it.text(), lambda t: hooks.run_hook(proj, path))

    def run_all_hooks(self):
        proj = self.project

        def work(t):
            for h in hooks.hook_dirs(proj):
                t.set_stage("Hook " + h.name)
                hooks.run_hook(proj, h)
        self.task("Run all hooks", work)

    # Boot files -------------------------------------------------------------------------
    def load_boot_file(self, rel):
        if rel:
            self.boot_edit.setPlainText((self.project.isodir / rel).read_text(errors="replace"))

    def save_boot_file(self):
        it = self.boot_files.currentItem()
        if it:
            (self.project.isodir / it.text()).write_text(self.boot_edit.toPlainText())
            self.project.record("edit-boot-file", it.text())
            self.main.stage_label.setText("Saved " + it.text())
