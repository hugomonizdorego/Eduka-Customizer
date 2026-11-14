"""What starts by itself in the distribution, and switching it on or off (Startup step).

Two kinds:

  services      start with the system, before anyone logs in: systemd units (or the init
                scripts of SysVinit, OpenRC and runit on systems without systemd)
  applications  start after a user logs in to the desktop: /etc/xdg/autostart/*.desktop

Services are switched on and off like `systemctl enable/disable` does (links in
/etc/systemd/system/*.wants). Applications get `Hidden=true` when they are off,
which every desktop understands. Services the system cannot start without are
listed but cannot be switched off.
"""

import configparser
import os
import re
from pathlib import Path

from disco.core import runner
from disco.core.log import log

UNIT_DIRS = ["etc/systemd/system", "usr/lib/systemd/system", "lib/systemd/system"]
AUTOSTART = "etc/xdg/autostart"
# Never switched off from here: the system would not start or nobody could log in.
ESSENTIAL = {"dbus.service", "dbus-broker.service", "live-config.service", "console-setup.service",
             "keyboard-setup.service", "getty@.service", "getty.target", "elogind.service", "udev.service",
             "networking.service"}
ESSENTIAL_PREFIXES = ("systemd-journald", "systemd-udevd", "systemd-logind", "systemd-tmpfiles",
                      "systemd-sysctl", "systemd-modules-load", "systemd-remount-fs", "systemd-user-sessions")
UNIT_KINDS = (".service", ".timer", ".socket", ".path")
NAME = re.compile(r"^[A-Za-z0-9@._:+-]+$")
# Plain-language names of common services.
FRIENDLY = {
    "NetworkManager.service": "Network connections (Wi-Fi, cable)", "ssh.service": "SSH server (remote login)",
    "cups.service": "Printing", "cups-browsed.service": "Finding network printers",
    "bluetooth.service": "Bluetooth", "avahi-daemon.service": "Finding computers as name.local",
    "cron.service": "Scheduled tasks (cron)", "anacron.service": "Scheduled tasks when the computer was off",
    "ufw.service": "Firewall (ufw)", "apparmor.service": "AppArmor security profiles",
    "unattended-upgrades.service": "Automatic security updates", "ModemManager.service": "Mobile broadband modems",
    "lightdm.service": "Login screen (LightDM)", "sddm.service": "Login screen (SDDM)",
    "gdm.service": "Login screen (GDM)", "gdm3.service": "Login screen (GDM)",
    "wpa_supplicant.service": "Wi-Fi security (WPA)", "rsyslog.service": "System log files",
    "smartmontools.service": "Disk health checks", "tlp.service": "Laptop battery saving",
    "fstrim.timer": "Trim SSDs once a week", "apt-daily.timer": "Download updates every day",
    "apt-daily-upgrade.timer": "Install updates every day", "man-db.timer": "Update the manual index",
    "e2scrub_all.timer": "Check ext4 file systems", "logrotate.timer": "Rotate log files",
    "plymouth-quit-wait.service": "Boot splash (Plymouth)", "speech-dispatcher.service": "Speech for screen readers",
    "disco-firstboot.service": "First start of the SD card (D!sco)",
    "eduka-flatpak-firstboot.service": "Install Flatpak apps at the first start (D!sco)",
}


def _is_essential(unit):
    return unit in ESSENTIAL or unit.startswith(ESSENTIAL_PREFIXES) or unit.split("@")[0] + "@.service" in ESSENTIAL


def init_of(rootfs):
    from disco.core import initsystem
    return initsystem.current(rootfs)


# Services (systemd) ----------------------------------------------------------------------------------------
def _unit_file(rootfs, unit):
    for d in UNIT_DIRS:
        p = Path(rootfs, d, unit)
        if p.is_file() or p.is_symlink():
            return p
    return None


def _read_unit(path):
    """{section: {key: value}} of a unit file (repeated keys joined with spaces)."""
    out, sec = {}, None
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            sec = out.setdefault(line[1:-1], {})
            continue
        if sec is not None and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            sec[k] = (sec[k] + " " + v).strip() if k in sec and k in ("WantedBy", "RequiredBy", "Also") else v
    return out


def _enabled_units(rootfs):
    """Units linked in a .wants/.requires folder of /etc/systemd/system (= enabled)."""
    base = Path(rootfs, "etc/systemd/system")
    found = set()
    if base.is_dir():
        for d in base.iterdir():
            if d.is_dir() and (d.name.endswith(".wants") or d.name.endswith(".requires")):
                for link in d.iterdir():
                    found.add(link.name)
    return found


def systemd_services(rootfs):
    rootfs = Path(rootfs)
    enabled = _enabled_units(rootfs)
    seen, out = set(), []
    for d in UNIT_DIRS:
        folder = rootfs / d
        if not folder.is_dir():
            continue
        for p in sorted(folder.iterdir()):
            unit = p.name
            if unit in seen or not unit.endswith(UNIT_KINDS) or "@." in unit:
                continue   # templates (getty@.service) are listed by their instances
            if p.is_symlink() and os.readlink(p) == "/dev/null":
                seen.add(unit)
                out.append({"unit": unit, "kind": "service", "enabled": False, "masked": True,
                            "description": FRIENDLY.get(unit, "Switched off for good (masked)"),
                            "essential": _is_essential(unit)})
                continue
            info = _read_unit(p)
            install = info.get("Install", {})
            if not (install.get("WantedBy") or install.get("RequiredBy")) and unit not in enabled:
                continue  # started by others when needed: nothing to switch
            seen.add(unit)
            desc = FRIENDLY.get(unit) or info.get("Unit", {}).get("Description", "")
            out.append({"unit": unit, "kind": "service", "enabled": unit in enabled, "masked": False,
                        "description": desc, "essential": _is_essential(unit)})
    # Enabled instances of templates (getty@tty1.service...)
    for unit in sorted(enabled - seen):
        if "@" in unit and unit.endswith(UNIT_KINDS):
            out.append({"unit": unit, "kind": "service", "enabled": True, "masked": False,
                        "description": FRIENDLY.get(unit, "Instance of " + unit.split("@")[0] + "@"),
                        "essential": _is_essential(unit)})
    return sorted(out, key=lambda s: (not s["enabled"], s["unit"].lower()))


def _systemctl(rootfs, action, unit):
    """systemctl --root works without a running system; fall back to the links it would make."""
    if runner.which("systemctl"):
        rc = runner.run(["systemctl", "--root=" + str(rootfs), "--no-reload", action, unit], check=False,
                        quiet=True)
        if rc == 0:
            return
        log.debug("systemctl --root %s %s failed, setting the links directly", action, unit)
    _links(rootfs, action, unit)


def _links(rootfs, action, unit):
    rootfs = Path(rootfs)
    base = rootfs / "etc/systemd/system"
    if action == "disable":
        if base.is_dir():
            for d in base.iterdir():
                if d.is_dir() and (d.name.endswith(".wants") or d.name.endswith(".requires")):
                    link = d / unit
                    if link.is_symlink() or link.exists():
                        link.unlink()
        return
    path = _unit_file(rootfs, unit) or _unit_file(rootfs, re.sub(r"@[^.]+\.", "@.", unit))
    if path is None:
        raise ValueError("No unit file for {}".format(unit))
    info = _read_unit(path).get("Install", {})
    targets = (info.get("WantedBy", "") + " " + info.get("RequiredBy", "")).split() or ["multi-user.target"]
    for t in targets:
        kind = ".requires" if t in info.get("RequiredBy", "").split() else ".wants"
        d = base / (t + kind)
        d.mkdir(parents=True, exist_ok=True)
        link = d / unit
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to("/" + str(path.relative_to(rootfs)))


# Services without systemd ------------------------------------------------------------------------------------
def sysv_services(rootfs, init):
    rootfs = Path(rootfs)
    out = []
    d = rootfs / "etc/init.d"
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir()):
        name = p.name
        if not p.is_file() or name in ("README", "skeleton", "rc", "rcS") or name.startswith("."):
            continue
        if init == "openrc":
            on = (rootfs / "etc/runlevels/default" / name).exists() or (rootfs / "etc/runlevels/boot" / name).exists()
        elif init == "runit":
            on = (rootfs / "etc/runit/runsvdir/default" / name).exists() or (
                (rootfs / "etc/rc2.d").is_dir() and bool(list((rootfs / "etc/rc2.d").glob("S??" + name))))
        else:
            on = bool(list((rootfs / "etc/rc2.d").glob("S??" + name))) if (rootfs / "etc/rc2.d").is_dir() else False
        desc = ""
        try:
            m = re.search(r"(?m)^# Short-Description:\s*(.*)$", p.read_text(errors="replace"))
            desc = m.group(1).strip() if m else ""
        except OSError:
            pass
        unit = name + ".service"
        out.append({"unit": name, "kind": "service", "enabled": on, "masked": False,
                    "description": FRIENDLY.get(unit) or desc, "essential": _is_essential(unit) or
                    name in ("dbus", "elogind", "udev", "eudev", "procps", "hostname.sh", "mountall.sh")})
    return sorted(out, key=lambda s: (not s["enabled"], s["unit"].lower()))


def services(project):
    init = init_of(project.rootfs)
    if init == "systemd":
        return systemd_services(project.rootfs)
    return sysv_services(project.rootfs, init)


def set_service(project, unit, enabled):
    if not NAME.match(unit):
        raise ValueError("Invalid service name: {}".format(unit))
    init = init_of(project.rootfs)
    name = unit
    if not enabled and _is_essential(unit if unit.endswith(UNIT_KINDS) else unit + ".service"):
        raise ValueError("{} is needed to start the system: it stays on".format(unit))
    if init == "systemd":
        if enabled and _unit_masked(project.rootfs, unit):
            _systemctl(project.rootfs, "unmask", unit)
        _systemctl(project.rootfs, "enable" if enabled else "disable", unit)
    else:
        from disco.core.chroot import Chroot
        with Chroot(project.rootfs) as ch:
            if init == "openrc":
                ch.run(["rc-update", "add" if enabled else "del", name, "default"], check=False)
            elif init == "runit" and Path(project.rootfs, "etc/sv", name).is_dir():
                link = Path(project.rootfs, "etc/runit/runsvdir/default", name)
                if enabled and not link.exists():
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to("/etc/sv/" + name)
                elif not enabled and (link.is_symlink() or link.exists()):
                    link.unlink()
            else:
                ch.run(["update-rc.d", name, "enable" if enabled else "disable"], check=False)
    project.state.setdefault("startup", {}).setdefault("services", {})[unit] = bool(enabled)
    project.save()
    project.record("startup-service", "{} {}".format(unit, "on" if enabled else "off"))
    log.info("Service %s: %s", unit, "starts with the system" if enabled else "off")


def _unit_masked(rootfs, unit):
    p = Path(rootfs, "etc/systemd/system", unit)
    return p.is_symlink() and os.readlink(p) == "/dev/null"


# Applications after login (XDG autostart) ---------------------------------------------------------------------------
def _desktop(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError, OSError):
        return None
    return cp if cp.has_section("Desktop Entry") else None


def applications(project):
    d = Path(project.rootfs) / AUTOSTART
    out = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.desktop")):
        cp = _desktop(p)
        if cp is None:
            continue
        e = cp["Desktop Entry"]
        hidden = e.get("Hidden", "false").lower() == "true" or \
            e.get("X-GNOME-Autostart-enabled", "true").lower() == "false"
        where = ""
        if e.get("OnlyShowIn"):
            where = "only in " + e.get("OnlyShowIn").strip(";").replace(";", ", ")
        elif e.get("NotShowIn"):
            where = "not in " + e.get("NotShowIn").strip(";").replace(";", ", ")
        out.append({"file": p.name, "name": e.get("Name", p.stem), "comment": e.get("Comment", ""),
                    "exec": e.get("Exec", ""), "enabled": not hidden, "where": where,
                    "custom": p.name.startswith("disco-")})
    return sorted(out, key=lambda a: (not a["enabled"], a["name"].lower()))


def _set_key(path, key, value):
    """Set (or remove, value None) one key of [Desktop Entry] and keep the rest of the file as it is."""
    lines = Path(path).read_text(errors="replace").splitlines()
    out, in_entry, done = [], False, False
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            if in_entry and not done and value is not None:
                at = len(out)
                while at > 0 and not out[at - 1].strip():
                    at -= 1          # before the blank lines that end the section
                out.insert(at, "{}={}".format(key, value))
                done = True
            in_entry = s == "[Desktop Entry]"
        elif in_entry and re.match(r"^{}\s*=".format(re.escape(key)), s):
            if value is not None and not done:
                out.append("{}={}".format(key, value))
                done = True
            continue
        out.append(line)
    if in_entry and not done and value is not None:
        out.append("{}={}".format(key, value))
    Path(path).write_text("\n".join(out) + "\n")


def set_application(project, file, enabled):
    if not re.match(r"^[A-Za-z0-9._+-]+\.desktop$", file):
        raise ValueError("Invalid autostart file: {}".format(file))
    p = Path(project.rootfs) / AUTOSTART / file
    if not p.is_file():
        raise FileNotFoundError("/{}/{} is not in the system".format(AUTOSTART, file))
    _set_key(p, "Hidden", None if enabled else "true")
    _set_key(p, "X-GNOME-Autostart-enabled", None if enabled else "false")
    project.record("startup-app", "{} {}".format(file, "on" if enabled else "off"))


def add_application(project, name, command, comment=""):
    """A program every user starts after logging in (an autostart entry of D!sco)."""
    name = name.strip()
    if not name or len(name) > 60 or any(c in name for c in "\n\r[]="):
        raise ValueError("Give the program a short name")
    if not command.strip() or "\n" in command:
        raise ValueError("Type the command to start, for example: firefox-esr https://example.org")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "program"
    p = Path(project.rootfs) / AUTOSTART / "disco-{}.desktop".format(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[Desktop Entry]\nType=Application\nName={}\nComment={}\nExec={}\nX-D!sco=added\n".format(
        name, comment.replace("\n", " "), command.strip()))
    project.record("startup-add", p.name)
    return p.name


def remove_application(project, file):
    if not file.startswith("disco-") or not file.endswith(".desktop") or "/" in file:
        raise ValueError("Only programs added in D!sco can be removed; switch the others off")
    p = Path(project.rootfs) / AUTOSTART / file
    if p.exists():
        p.unlink()
    project.record("startup-remove", file)
