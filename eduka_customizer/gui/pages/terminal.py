"""Terminal & Live page: live edit session, chroot terminal, hooks, files."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from eduka_customizer.qt.core import QTimer
from eduka_customizer.qt.widgets import QFileDialog, QLineEdit, QListWidget, QMessageBox

from eduka_customizer.core import hooks
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
    nav_title = "Terminal & Live"
    subtitle = ("Step 11 · For experts: start the system's desktop in a window and change things by hand, use a "
                "root terminal, or run scripts. Everything ends up in the ISO.")
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

        c = self.card("Install applications",
                      "Three ways, all installing straight into the image: type package names, use the "
                      "Synaptic package manager in a window, or work in a root terminal.")
        self.apt_line = QLineEdit()
        self.apt_line.setPlaceholderText("package names, e.g. vlc gimp gcompris-qt")
        self.apt_line.returnPressed.connect(self.apt_install)
        c.add(hbox(self.apt_line, button("Install with APT", self.apt_install, "primary")))
        c.add(hbox(button("Synaptic package manager (window)", self.synaptic, icon_names=("synaptic",)),
                   button("Terminal in the image", self.open_terminal, icon_names=("utilities-terminal",)),
                   button("Search on the Packages page", lambda: self.main.go("PackagesPage")), None))

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

    # Applications --------------------------------------------------------------------
    def apt_install(self):
        names = self.apt_line.text().split()
        if names:
            from eduka_customizer.core.apt import Packages
            proj = self.project
            self.task("Install " + " ".join(names), lambda t: Packages(proj).install(names),
                      lambda _r: self.apt_line.clear())

    def synaptic(self):
        if not (self.project.rootfs / "usr/sbin/synaptic").exists():
            if QMessageBox.question(self, "Synaptic", "Synaptic is not installed in the image. Install it now?") != \
                    QMessageBox.StandardButton.Yes:
                return
            from eduka_customizer.core.apt import Packages
            proj = self.project
            self.task("Install Synaptic", lambda t: Packages(proj).install(["synaptic"]),
                      lambda _r: self._start_synaptic())
            return
        self._start_synaptic()

    def _start_synaptic(self):
        if self.main.live and self.main.live.running:
            self.main.live.run_app("synaptic", home="/root")
            return
        if self.main.task:
            QMessageBox.information(self, "Synaptic", "Wait for the running task to finish.")
            return
        live = LiveSession(self.project)
        try:
            display = live.start(resolution=self.resolution.currentText(), mode="root", command="synaptic")
        except Exception as e:
            QMessageBox.warning(self, "Synaptic", str(e))
            return
        self.main.live = live
        self.live_state.setText("Synaptic is running on display :{} - close it when done".format(display))
        self.poll.start(1500)

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
        from eduka_customizer.gui.opener import open_url
        open_url(path)

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
