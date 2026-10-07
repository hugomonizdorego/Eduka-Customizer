"""Desktop environments, window managers, sessions and display managers."""

import configparser
import json
import os
from pathlib import Path

from eduka_customizer.core.apt import Packages
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.config import data_file
from eduka_customizer.core.log import log

_catalog = None


def catalog():
    global _catalog
    if _catalog is None:
        with open(data_file("desktops.json"), encoding="utf-8") as fh:
            _catalog = json.load(fh)
    return _catalog


def desktop(de_id):
    for d in catalog()["desktops"]:
        if d["id"] == de_id:
            return d
    raise KeyError("Unknown desktop: {}".format(de_id))


def display_manager(dm_id):
    for d in catalog()["display_managers"]:
        if d["id"] == dm_id:
            return d
    raise KeyError("Unknown display manager: {}".format(dm_id))


def _read_desktop_entry(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(path, encoding="utf-8")
        return dict(cp["Desktop Entry"]) if cp.has_section("Desktop Entry") else {}
    except (configparser.Error, UnicodeDecodeError):
        return {}


def sessions(rootfs):
    """List sessions installed in the image: dicts with id, name, exec, type."""
    rootfs = Path(rootfs)
    result = []
    for kind, rel in (("x11", "usr/share/xsessions"), ("wayland", "usr/share/wayland-sessions")):
        d = rootfs / rel
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            e = _read_desktop_entry(f)
            if not e or e.get("hidden", "").lower() == "true":
                continue
            result.append({"id": f.stem, "name": e.get("name", f.stem), "exec": e.get("exec", ""),
                           "type": kind, "desktop_names": e.get("desktopnames", "")})
    return result


def detect_display_manager(rootfs):
    rootfs = Path(rootfs)
    ddm = rootfs / "etc/X11/default-display-manager"
    if ddm.is_file():
        name = os.path.basename(ddm.read_text().strip())
        if name:
            return name
    link = rootfs / "etc/systemd/system/display-manager.service"
    if link.is_symlink():
        return Path(os.readlink(link)).stem
    for dm in ("lightdm", "sddm", "gdm3", "lxdm"):
        if (rootfs / "usr/sbin" / dm).exists() or (rootfs / "usr/bin" / dm).exists():
            return dm
    return ""


def installed_desktops(rootfs):
    have = {s["id"] for s in sessions(rootfs)}
    return [d["id"] for d in catalog()["desktops"] if d["session"] in have]


class DesktopManager:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.pkgs = Packages(project)
        self.chroot = Chroot(project.rootfs)

    def install(self, de_id, dm_id=None, remove_others=False, no_recommends=False):
        d = desktop(de_id)
        log.info("Installing desktop: %s", d["name"])
        with self.chroot:
            if remove_others:
                self.remove_other_desktops(keep=de_id)
            self.pkgs.install(d["packages"], no_recommends=no_recommends)
            if d.get("eduka_desktop"):
                from eduka_customizer.core.eduka_desktop import EdukaDesktop
                EdukaDesktop(self.project).fetch_build_install()
            dm_id = dm_id or (detect_display_manager(self.rootfs) or d.get("dm"))
            if dm_id:
                self.set_display_manager(dm_id)
            self.set_default_session(d["session"])
        self.project.record("desktop-install", de_id)

    def remove_other_desktops(self, keep):
        tasks = [d["task"] for d in catalog()["desktops"]
                 if d.get("task") and d["id"] != keep and self.pkgs.is_installed(d["task"])]
        if tasks:
            log.info("Removing other desktop tasks: %s", " ".join(tasks))
            self.pkgs.remove(tasks, purge=True, autoremove=True)

    def set_display_manager(self, dm_id):
        dm = display_manager(dm_id)
        service = dm.get("service", dm_id)
        with self.chroot:
            missing = [p for p in dm["packages"] if not self.pkgs.is_installed(p)]
            if missing:
                self.pkgs.install(missing, update=False)
            log.info("Default display manager: %s", dm["name"])
            Path(self.rootfs, "etc/X11").mkdir(parents=True, exist_ok=True)
            Path(self.rootfs, "etc/X11/default-display-manager").write_text(dm["binary"] + "\n")
            self.chroot.run(["debconf-set-selections"],
                            input="{} shared/default-x-display-manager select {}\n".format(service, service))
            link = Path(self.rootfs, "etc/systemd/system/display-manager.service")
            if link.is_symlink() or link.exists():
                link.unlink()
            unit = "/lib/systemd/system/{}.service".format(service)
            if not Path(self.rootfs, unit.lstrip("/")).exists():
                unit = "/usr/lib/systemd/system/{}.service".format(service)
            link.symlink_to(unit)
            if dm_id == "lightdm-slick":
                self._lightdm_conf({"greeter-session": "slick-greeter"})
            elif dm_id == "lightdm":
                self._lightdm_conf({"greeter-session": "lightdm-gtk-greeter"})
        self.project.record("display-manager", dm_id)

    def _lightdm_conf(self, values):
        p = Path(self.rootfs, "etc/lightdm/lightdm.conf.d/50-edukasaun.conf")
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        if p.exists():
            cp.read(p)
        if not cp.has_section("Seat:*"):
            cp.add_section("Seat:*")
        for k, v in values.items():
            cp.set("Seat:*", k, v)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as fh:
            cp.write(fh)

    def set_default_session(self, session_id):
        """Make *session_id* the default for the display manager and live user."""
        sess = {s["id"]: s for s in sessions(self.rootfs)}
        if session_id not in sess:
            log.warning("Session %s is not installed yet", session_id)
        log.info("Default session: %s", session_id)
        self._lightdm_conf({"user-session": session_id, "autologin-session": session_id})
        sddm = Path(self.rootfs, "etc/sddm.conf.d/50-edukasaun.conf")
        if Path(self.rootfs, "usr/bin/sddm").exists():
            sddm.parent.mkdir(parents=True, exist_ok=True)
            cp = configparser.ConfigParser(interpolation=None)
            cp.optionxform = str
            if sddm.exists():
                cp.read(sddm)
            if not cp.has_section("Autologin"):
                cp.add_section("Autologin")
            cp.set("Autologin", "Session", session_id + ".desktop")
            with open(sddm, "w") as fh:
                cp.write(fh)
        # /etc/skel/.dmrc is honoured by several display managers.
        Path(self.rootfs, "etc/skel/.dmrc").write_text("[Desktop]\nSession={}\n".format(session_id))
        # x-session-manager alternative for startx and fallbacks.
        entry = sess.get(session_id)
        if entry and entry["exec"]:
            exe = entry["exec"].split()[0]
            if not exe.startswith("/"):
                for d in ("usr/bin", "usr/local/bin"):
                    if Path(self.rootfs, d, exe).exists():
                        exe = "/" + d + "/" + exe
                        break
            if exe.startswith("/") and Path(self.rootfs, exe.lstrip("/")).exists():
                self.chroot.run(["update-alternatives", "--install", "/usr/bin/x-session-manager",
                                 "x-session-manager", exe, "90"], check=False, quiet=True)
                self.chroot.run(["update-alternatives", "--set", "x-session-manager", exe],
                                check=False, quiet=True)
        self.project.state.setdefault("desktop", {})["session"] = session_id
        self.project.save()

    def set_lxqt_window_manager(self, wm):
        p = Path(self.rootfs, "etc/xdg/lxqt/session.conf")
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        if p.exists():
            cp.read(p)
        if not cp.has_section("General"):
            cp.add_section("General")
        cp.set("General", "window_manager", wm)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as fh:
            cp.write(fh)
        log.info("LXQt window manager: %s", wm)
