"""Live edit: run the image's desktop in a nested X server (Xephyr).

Everything changed inside the session is written straight into the root
filesystem, so it ends up in the next ISO build.  In "skel" mode the
session's home is /etc/skel, which makes the changes the defaults of
every new user, including the live user.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.desktop import sessions
from eduka_customizer.core.log import log

MODES = {
    "skel": "Save as default for all users (/etc/skel)",
    "root": "Run as root (system settings only)",
    "sandbox": "Test only (temporary home, discarded)",
}


def free_display():
    for n in range(10, 60):
        if not os.path.exists("/tmp/.X11-unix/X{}".format(n)) and not os.path.exists("/tmp/.X{}-lock".format(n)):
            return n
    raise RuntimeError("No free X display number")


class LiveSession:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.chroot = Chroot(project.rootfs, x11=True)
        self.xephyr = None
        self.session = None
        self.display = None
        self.mode = "skel"
        self._entered = False

    @property
    def running(self):
        if self.session is not None and self.session.poll() is not None:
            return False  # the desktop or program ended; the empty window is closed by stop()
        return self.xephyr is not None and self.xephyr.poll() is None

    def _home(self):
        if self.mode == "skel":
            return "/etc/skel"
        if self.mode == "root":
            return "/root"
        home = "/tmp/eduka-sandbox-home"
        target = self.rootfs / home.lstrip("/")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.rootfs / "etc/skel", target, symlinks=True)
        return home

    def start(self, session_id=None, resolution="1280x800", mode="skel", command=None):
        if self.running:
            raise RuntimeError("A live session is already running")
        runner.require("Xephyr")
        self.mode = mode if mode in MODES else "skel"
        available = {s["id"]: s for s in sessions(self.rootfs) if s["type"] == "x11"}
        if command is None:
            if not available:
                raise RuntimeError("No X11 session is installed in the image. Install a desktop first.")
            sess = available.get(session_id) or available.get(
                self.project.state.get("desktop", {}).get("session", "")) or next(iter(available.values()))
            command = sess["exec"]
            desktop_names = sess["desktop_names"] or sess["name"]
            log.info("Starting %s in a nested window", sess["name"])
        else:
            desktop_names = ""
        if "gnome-session" in command or "gnome-shell" in command:
            log.warning("GNOME needs systemd user services and usually does not start in a chroot")

        self.display = free_display()
        self.xephyr = subprocess.Popen(
            [runner.which("Xephyr"), ":{}".format(self.display), "-ac", "-br", "-noreset",
             "-resizeable", "-screen", resolution, "-title",
             "Eduka-Customizer live session (changes are saved to the image)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        sock = Path("/tmp/.X11-unix/X{}".format(self.display))
        for _ in range(100):
            if sock.exists() or self.xephyr.poll() is not None:
                break
            time.sleep(0.1)
        if not sock.exists():
            self.stop()
            raise RuntimeError("Xephyr did not start")

        self.chroot.__enter__()
        self._entered = True
        home = self._home()
        runtime = self.rootfs / "run/eduka-live-runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        runtime.chmod(0o700)
        env = {
            "DISPLAY": ":{}".format(self.display),
            "HOME": home,
            "XDG_CONFIG_HOME": home + "/.config",
            "XDG_DATA_HOME": home + "/.local/share",
            "XDG_CACHE_HOME": "/tmp/eduka-live-cache",
            "XDG_RUNTIME_DIR": "/run/eduka-live-runtime",
            "XDG_SESSION_TYPE": "x11",
            "XDG_CURRENT_DESKTOP": desktop_names.replace(";", ":").strip(":"),
            "QT_LINUX_ACCESSIBILITY_ALWAYS_ON": "1",
            "NO_AT_BRIDGE": "1",
            "LANG": self.project.state.get("locale", {}).get("default", "C.UTF-8"),
        }
        env.pop("LC_ALL", None)
        wrapper = "exec dbus-run-session -- {}".format(command) if (
            self.rootfs / "usr/bin/dbus-run-session").exists() else "exec " + command
        cmd = self.chroot.command(["/bin/sh", "-c", wrapper], env=env, interactive=True)
        # LC_ALL from the default environment would override LANG in the desktop.
        cmd = [c for c in cmd if not c.startswith("LC_ALL=")]
        self.session = subprocess.Popen(cmd, stdout=open(self.project.logs / "live-session.log", "w"),
                                        stderr=subprocess.STDOUT, start_new_session=True)
        self.project.record("live-session", "{} ({})".format(command, self.mode))
        return self.display

    def run_app(self, command, home=None):
        """Start one more program inside the running nested session."""
        if not self.running:
            raise RuntimeError("Start a live session first")
        env = {"DISPLAY": ":{}".format(self.display), "HOME": home or self._current_home(),
               "XDG_RUNTIME_DIR": "/run/eduka-live-runtime"}
        subprocess.Popen(self.chroot.command(["/bin/sh", "-c", command], env=env, interactive=True),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def _current_home(self):
        return {"skel": "/etc/skel", "root": "/root"}.get(self.mode, "/tmp/eduka-sandbox-home")

    def wait(self):
        if self.session:
            self.session.wait()

    def stop(self):
        for proc in (self.session, self.xephyr):
            if proc and proc.poll() is None:
                try:
                    os.killpg(proc.pid, 15)
                    proc.wait(10)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(proc.pid, 9)
                    except ProcessLookupError:
                        pass
        # Programs started inside the chroot that outlived the session.
        self._kill_chroot_processes()
        self.session = None
        self.xephyr = None
        if self._entered:
            self._entered = False
            self.chroot.__exit__(None, None, None)
        self._tidy_home()

    def _kill_chroot_processes(self):
        if self.display is None:
            return
        root = str(self.rootfs.resolve())
        marker = "DISPLAY=:{}".format(self.display).encode()
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                if os.readlink("/proc/{}/root".format(pid)) != root:
                    continue
                with open("/proc/{}/environ".format(pid), "rb") as fh:
                    if marker in fh.read().split(b"\0"):
                        os.kill(int(pid), 15)
            except OSError:
                continue

    def _tidy_home(self):
        base = self.rootfs / "etc/skel"
        if self.mode == "sandbox":
            shutil.rmtree(self.rootfs / "tmp/eduka-sandbox-home", ignore_errors=True)
        elif self.mode == "skel":
            for rel in (".cache", ".xsession-errors", ".Xauthority", ".dbus",
                        ".local/share/recently-used.xbel", ".bash_history"):
                p = base / rel
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p, ignore_errors=True)
                elif p.exists() or p.is_symlink():
                    p.unlink()
            leaked = []
            for f in (base / ".config").rglob("*") if (base / ".config").is_dir() else []:
                try:
                    if f.is_file() and f.stat().st_size < 1 << 20 and b"/etc/skel" in f.read_bytes():
                        leaked.append(str(f.relative_to(base)))
                except OSError:
                    continue
            if leaked:
                log.warning("These files mention /etc/skel and may need review: %s", ", ".join(leaked[:20]))
        shutil.rmtree(self.rootfs / "tmp/eduka-live-cache", ignore_errors=True)
