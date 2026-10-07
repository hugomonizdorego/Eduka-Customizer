"""Desktop environments, window managers, sessions and display managers."""

import configparser
import json
import os
import re
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
                self.pkgs.update()
                unavailable = set(missing) - self.pkgs.available(missing)
                if unavailable:
                    raise RuntimeError("{} is not available in this Debian suite (missing: {})".format(
                        dm["name"], " ".join(sorted(unavailable))))
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
            if dm.get("greeter"):
                self._lightdm_conf({"greeter-session": dm["greeter"]})
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

    # Login screen themes ------------------------------------------------
    def set_sddm_theme(self, theme):
        pkg = dict(catalog().get("sddm_themes", [])).get(theme)
        with self.chroot:
            if pkg and not self.pkgs.is_installed(pkg):
                self.pkgs.install([pkg])
            if not Path(self.rootfs, "usr/share/sddm/themes", theme).is_dir():
                raise RuntimeError("SDDM theme not installed: {}".format(theme))
        p = Path(self.rootfs, "etc/sddm.conf.d/10-edukasaun-theme.conf")
        p.parent.mkdir(parents=True, exist_ok=True)
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        if p.exists():
            cp.read(p)
        if not cp.has_section("Theme"):
            cp.add_section("Theme")
        cp.set("Theme", "Current", theme)
        with open(p, "w") as fh:
            cp.write(fh)
        self.project.record("sddm-theme", theme)

    # X11 or Wayland ------------------------------------------------------
    def session_types(self, de_id):
        return sorted(desktop(de_id).get("sessions", {}).keys() & {"x11", "wayland"})

    def set_session_type(self, de_id, kind):
        d = desktop(de_id)
        sess = d.get("sessions", {})
        if kind not in sess:
            raise ValueError("{} has no {} session".format(d["name"], "Wayland" if kind == "wayland" else "X11"))
        with self.chroot:
            extra = sess.get(kind + "_packages", [])
            missing = [p for p in extra if not self.pkgs.is_installed(p)]
            if missing:
                self.pkgs.install(missing)
            self.set_default_session(sess[kind])
        gdm = Path(self.rootfs, "etc/gdm3/daemon.conf")
        if gdm.exists():
            text = gdm.read_text()
            value = "true" if kind == "wayland" else "false"
            if re.search(r"(?m)^#?\s*WaylandEnable\s*=", text):
                text = re.sub(r"(?m)^#?\s*WaylandEnable\s*=.*$", "WaylandEnable=" + value, text)
            else:
                text = text.replace("[daemon]", "[daemon]\nWaylandEnable=" + value, 1)
            gdm.write_text(text)
        if Path(self.rootfs, "usr/bin/sddm").exists() and kind == "x11":
            p = Path(self.rootfs, "etc/sddm.conf.d/20-edukasaun-display.conf")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("[General]\nDisplayServer=x11\n")
        self.project.state.setdefault("desktop", {})["session_type"] = kind
        self.project.save()
        log.info("Default session type: %s", kind)

    # Compositor ---------------------------------------------------------
    def set_compositor(self, comp_id, preset="shadows"):
        comps = {c["id"]: c for c in catalog()["compositors"]}
        if comp_id not in comps:
            raise KeyError("Unknown compositor: {}".format(comp_id))
        c = comps[comp_id]
        r = self.rootfs
        with self.chroot:
            pk = [p for p in c.get("packages", []) if not self.pkgs.is_installed(p)]
            if pk:
                self.pkgs.install(pk)
        skel_auto = Path(r, "etc/skel/.config/autostart")
        if c["kind"] == "x11":
            for name in ("picom", "xcompmgr"):
                f = skel_auto / (name + ".desktop")
                if name == comp_id:
                    if f.exists():
                        f.unlink()
                    if name == "xcompmgr":
                        skel_auto.mkdir(parents=True, exist_ok=True)
                        f.write_text("[Desktop Entry]\nType=Application\nName=xcompmgr\n"
                                     "Exec=xcompmgr -c -f -n\nNoDisplay=true\n")
                elif name == "picom" or f.exists():
                    skel_auto.mkdir(parents=True, exist_ok=True)
                    f.write_text("[Desktop Entry]\nType=Application\nName={}\nExec={}\nHidden=true\n".format(name, name))
            if comp_id == "picom":
                Path(r, "etc/xdg").mkdir(parents=True, exist_ok=True)
                Path(r, "etc/xdg/picom.conf").write_text(PICOM.get(preset, PICOM["shadows"]))
                if not Path(r, "etc/xdg/autostart/picom.desktop").exists():
                    Path(r, "etc/xdg/autostart").mkdir(parents=True, exist_ok=True)
                    Path(r, "etc/xdg/autostart/picom.desktop").write_text(
                        "[Desktop Entry]\nType=Application\nName=picom\nExec=picom\nNoDisplay=true\n")
            xfwm = Path(r, "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml")
            if xfwm.exists():
                on = "true" if comp_id == "builtin" else "false"
                text = xfwm.read_text()
                text = re.sub(r'(<property name="use_compositing" type="bool" value=")\w+(")',
                              lambda m: m.group(1) + on + m.group(2), text)
                xfwm.write_text(text)
            marco = "true" if comp_id == "builtin" else "false"
            Path(r, "usr/share/glib-2.0/schemas").mkdir(parents=True, exist_ok=True)
            Path(r, "usr/share/glib-2.0/schemas/92_eduka-compositor.gschema.override").write_text(
                "[org.mate.Marco.general]\ncompositing-manager={}\n".format(marco))
            if Path(r, "usr/bin/glib-compile-schemas").exists():
                self.chroot.run(["glib-compile-schemas", "/usr/share/glib-2.0/schemas"], check=False, quiet=True)
        else:
            # LXQt Wayland session: compositor used by lxqt-wayland-session.
            conf = Path(r, "etc/xdg/lxqt/session.conf")
            cp = configparser.ConfigParser(interpolation=None)
            cp.optionxform = str
            if conf.exists():
                cp.read(conf)
            if not cp.has_section("General"):
                cp.add_section("General")
            cp.set("General", "compositor", comp_id)
            conf.parent.mkdir(parents=True, exist_ok=True)
            with open(conf, "w") as fh:
                cp.write(fh)
        self.project.state.setdefault("desktop", {})["compositor"] = {"id": comp_id, "preset": preset}
        self.project.record("compositor", "{} {}".format(comp_id, preset))
        log.info("Compositor: %s (%s)", c["name"], preset)


PICOM = {
    "light": "# picom (Eduka-Customizer preset: light)\nbackend = \"xrender\";\nvsync = true;\n"
             "shadow = false;\nfading = true;\nfade-delta = 6;\n",
    "shadows": "# picom (Eduka-Customizer preset: shadows)\nbackend = \"xrender\";\nvsync = true;\n"
               "shadow = true;\nshadow-radius = 12;\nshadow-opacity = 0.35;\nshadow-offset-x = -10;\n"
               "shadow-offset-y = -10;\nshadow-exclude = [ \"class_g = 'eduka-panel'\", \"_GTK_FRAME_EXTENTS@:c\" ];\n"
               "fading = true;\nfade-delta = 5;\ncorner-radius = 8;\n",
    "glass": "# picom (Eduka-Customizer preset: glass, needs OpenGL)\nbackend = \"glx\";\nvsync = true;\n"
             "shadow = true;\nshadow-radius = 16;\nshadow-opacity = 0.3;\nfading = true;\n"
             "blur-method = \"dual_kawase\";\nblur-strength = 6;\nblur-background = true;\n"
             "corner-radius = 12;\nblur-background-exclude = [ \"window_type = 'desktop'\" ];\n",
    "off": "# picom disabled effects\nbackend = \"xrender\";\nshadow = false;\nfading = false;\n",
}
