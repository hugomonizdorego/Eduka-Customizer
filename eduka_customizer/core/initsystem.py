"""The init system of the distribution: systemd or an alternative.

systemd is more than a boot loader: it is the first program the kernel starts
(PID 1) and a whole suite around it (logins, devices, services, journal). Debian
uses it; Devuan and its derivatives do without it. The alternatives that work
with everything DistroForge builds (the kernel and initramfs, live-boot and
live-config, every boot loader, the Calamares installer, desktops through
elogind) are:

  SysVinit   Debian's classic init; Devuan's default.
  OpenRC     dependency-based services (Gentoo, Alpine), started by SysVinit's init.
  runit      tiny and fast supervision (Void Linux), runs Debian's init scripts at boot.

s6 and GNU Shepherd are listed with the reason they cannot be chosen: Debian and
Devuan package them, but not as an init for a whole system (no service scripts
for Debian's packages, no live-config or Calamares support), so an ISO with them
would not start its services.
"""

import re
from pathlib import Path

from eduka_customizer.core.log import log

# id: (name, description, packages, live-config backend, Calamares services module)
INITS = {
    "systemd": ("systemd", "Debian's default: fast parallel start, logins, devices and services in one suite. "
                "Needed by GNOME.", ["systemd-sysv"], "live-config-systemd", "services-systemd"),
    "sysvinit": ("SysVinit", "The classic init with shell scripts in /etc/init.d: simple and well known, "
                 "Devuan's default.", ["sysvinit-core", "sysv-rc"], "live-config-sysvinit", ""),
    "openrc": ("OpenRC", "Dependency-based services from Gentoo and Alpine, started in parallel; uses the same "
               "init scripts.", ["openrc", "sysvinit-core"], "live-config-sysvinit", "services-openrc"),
    "runit": ("runit", "Very small and fast service supervision from Void Linux; runs the init scripts at "
              "boot, then supervises.", ["runit-init", "runit"], "live-config-sysvinit", ""),
}
# Desktops (and more) need logind: elogind gives them their sessions without systemd.
WITHOUT_SYSTEMD = ["elogind", "libpam-elogind"]
# Debian dropped some init scripts; this package has them (Devuan ships them itself).
ORPHAN_SCRIPTS = "orphan-sysvinit-scripts"
NOT_AVAILABLE = [
    ("s6", "s6", "Debian and Devuan package s6 as a supervision suite, not as the init of a whole system: no "
                 "service scripts for Debian's packages, no live-config or Calamares support."),
    ("shepherd", "GNU Shepherd", "The init of GNU Guix, written in Guile Scheme. Debian has it as a user "
                                 "service manager only; it cannot start a Debian system."),
]
# Desktops that do not start without systemd (their session needs systemd's user manager).
NEEDS_SYSTEMD = {"gnome-shell": "GNOME", "gnome-flashback": "GNOME Flashback"}
ALL_INIT_PACKAGES = {"systemd-sysv", "sysvinit-core", "openrc", "runit-init"}
LIVE_BACKENDS = {"live-config-systemd", "live-config-sysvinit"}


def _installed(rootfs):
    from eduka_customizer.core.apt import is_installed_status, parse_deb822
    status = Path(rootfs, "var/lib/dpkg/status")
    if not status.is_file():
        return set()
    return {st.get("Package") for st in parse_deb822(status.read_text(errors="replace"))
            if is_installed_status(st.get("Status", ""))}


def current(rootfs):
    """The init system of the image (from its packages, or what /sbin/init is)."""
    have = _installed(rootfs)
    if "runit-init" in have:
        return "runit"
    if "openrc" in have and "sysvinit-core" in have:
        return "openrc"
    if "sysvinit-core" in have and "systemd-sysv" not in have:
        return "sysvinit"
    if "systemd-sysv" in have:
        return "systemd"
    init = Path(rootfs, "sbin/init") if Path(rootfs, "sbin/init").exists() else Path(rootfs, "usr/sbin/init")
    if init.is_symlink() and "systemd" in str(init.readlink()):
        return "systemd"
    if init.exists() and not init.is_symlink():
        return "sysvinit"
    return "systemd"


def live_packages(rootfs):
    """The live-boot packages a live system with this init system needs."""
    return ["live-boot", "live-config", INITS[current(rootfs)][3]]


def options(project):
    """[(id, name, description, usable, reason, in use)]."""
    r = Path(project.rootfs)
    cur = current(r)
    have = _installed(r)
    blocker = next((name for pkg, name in NEEDS_SYSTEMD.items() if pkg in have), "")
    out = []
    for iid, (name, desc, _p, _l, _c) in INITS.items():
        ok, why = True, ""
        if iid != "systemd" and blocker:
            ok, why = False, "{} is installed and needs systemd".format(blocker)
        out.append((iid, name, desc, ok, why, iid == cur))
    for iid, name, why in NOT_AVAILABLE:
        out.append((iid, name, why, False, why, False))
    return out


def check(project):
    """[(level, text)] about the init system and what depends on it."""
    r = Path(project.rootfs)
    cur = current(r)
    have = _installed(r)
    out = []
    if cur != "systemd":
        blocker = [name for pkg, name in NEEDS_SYSTEMD.items() if pkg in have]
        if blocker:
            out.append(("fail", "{} needs systemd, but the init system is {}: choose systemd or another "
                                "desktop".format(", ".join(blocker), INITS[cur][0])))
        if "elogind" not in have and any(p in have for p in ("xserver-xorg-core", "xwayland")):
            out.append(("warn", "elogind is missing: desktops need it without systemd (install elogind and "
                                "libpam-elogind)"))
        if INITS[cur][3] not in have and "live-config" in have:
            out.append(("warn", "{} is missing: live-config cannot set up the live system".format(INITS[cur][3])))
        from eduka_customizer.core.bootchoice import BootChoice
        if BootChoice(project).current() == "systemd-boot" and \
                not Path(r, "usr/bin/kernel-install").exists():
            out.append(("fail", "systemd-boot needs kernel-install from systemd: choose another boot loader"))
    return out or [("ok", "{} starts the system".format(INITS[cur][0]))]


# Services DistroForge adds to the image -------------------------------------------------
SYSV_SCRIPT = """#!/bin/sh
### BEGIN INIT INFO
# Provides:          {name}
# Required-Start:    $local_fs $remote_fs{network}
# Required-Stop:     $local_fs $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 6
# Short-Description: {description}
### END INIT INFO
# Written by DistroForge from /etc/systemd/system/{name}.service for init systems without systemd.

case "$1" in
    start) {start} ;;
    stop) {stop} ;;
    restart|force-reload) "$0" stop; "$0" start ;;
    status) exit 0 ;;
    *) echo "Usage: $0 start|stop|restart" >&2; exit 3 ;;
esac
exit 0
"""


def sysv_from_unit(project, unit_path):
    """Write /etc/init.d/<name> doing what a simple oneshot unit of DistroForge does."""
    unit_path = Path(unit_path)
    text = unit_path.read_text(errors="replace")
    name = unit_path.stem
    if not re.match(r"^[a-z0-9-]+$", name):
        raise ValueError("Invalid service name: {}".format(name))

    def value(key):
        m = re.search(r"(?m)^{}=(.*)$".format(key), text)
        return m.group(1).strip() if m else ""
    start = value("ExecStart") or "true"
    stop = value("ExecStop") or "true"
    network = " $network" if "network" in text else ""
    if "flatpak" in name:
        start = "({} &)".format(start)  # waits for the network: never hold up the boot
    script = Path(project.rootfs, "etc/init.d", name)
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(SYSV_SCRIPT.format(name=name, description=value("Description") or name, start=start,
                                         stop=stop, network=network))
    script.chmod(0o755)
    return name


def sync_services(project, chroot=None):
    """Give DistroForge's own systemd services an init script when systemd is not the init system."""
    r = Path(project.rootfs)
    if current(r) == "systemd":
        return []
    names = []
    for unit in sorted(Path(r, "etc/systemd/system").glob("eduka-*.service")):
        wants = Path(r, "etc/systemd/system/multi-user.target.wants", unit.name)
        if not (wants.exists() or wants.is_symlink()):
            continue
        names.append(sysv_from_unit(project, unit))
    if names:
        from eduka_customizer.core.chroot import Chroot
        ch = chroot or Chroot(project.rootfs)
        with ch:
            for n in names:
                ch.run(["update-rc.d", n, "defaults"], check=False, quiet=True)
        log.info("Init scripts written for: %s", ", ".join(names))
    return names


# Calamares ----------------------------------------------------------------------------------
def wire_calamares(project, init_id):
    """Use the services module of *init_id* in the installer (or none) and fit machineid."""
    from eduka_customizer.core.calamares import Calamares
    cal = Calamares(project)
    if not cal.installed() or not cal.settings_path().exists():
        return False
    module = INITS[init_id][4]
    settings = cal.read("settings")
    seq, placed = [], False
    for step in settings.get("sequence") or []:
        if isinstance(step, dict) and "exec" in step:
            new = []
            for m in step.get("exec") or []:
                if m in ("services-systemd", "services-openrc"):
                    if module and not placed:
                        new.append(module)
                        placed = True
                    continue
                new.append(m)
            if module and not placed and "displaymanager" in new:
                new.insert(new.index("displaymanager") + 1, module)
                placed = True
            step = dict(step, exec=new)
        seq.append(step)
    cal.write("settings", {"sequence": seq})
    if module == "services-openrc":
        conf = cal.etc / "modules/services-openrc.conf"
        if not conf.exists():
            conf.parent.mkdir(parents=True, exist_ok=True)
            conf.write_text("---\n# Written by DistroForge: services of the installed system (OpenRC).\n"
                            "initdDir: /etc/init.d\nrunlevelsDir: /etc/runlevels\nservices:\n"
                            "    - name: elogind\n      runlevel: boot\n      mandatory: false\n")
    mid = cal.etc / "modules/machineid.conf"
    if mid.exists() or (Path(project.rootfs) / "usr/share/calamares/modules/machineid.conf").exists():
        has_tool = Path(project.rootfs, "usr/bin/systemd-machine-id-setup").exists()
        cal.write("machineid", {"systemd": init_id == "systemd" and has_tool, "dbus": True, "dbus-symlink": True})
    return True


# Switching ----------------------------------------------------------------------------------
def use(project, init_id):
    """Make *init_id* the init system of the image, with everything that has to change with it."""
    if init_id not in INITS:
        known = dict((i, w) for i, _n, w in NOT_AVAILABLE)
        raise ValueError(known.get(init_id) or "Unknown init system: {} (use {})".format(
            init_id, ", ".join(INITS)))
    usable = {o[0]: o for o in options(project)}[init_id]
    if not usable[3]:
        raise ValueError("{} cannot be used: {}".format(usable[1], usable[4]))
    from eduka_customizer.core.apt import APT, Packages
    r = Path(project.rootfs)
    name, _d, packages, live, _m = INITS[init_id]
    have = _installed(r)
    want = list(packages) + ([live] if "live-config" in have or "live-boot" in have else [])
    if init_id != "systemd":
        want += WITHOUT_SYSTEMD
    pk = Packages(project)
    with pk.chroot:
        pk.update()
        if init_id != "systemd" and not Path(r, "etc/devuan_version").exists() and pk.available([ORPHAN_SCRIPTS]):
            want.append(ORPHAN_SCRIPTS)
        lacking = [p for p in want if p not in pk.available(want)]
        if lacking:
            raise RuntimeError("{} is not available from the repositories of the image: {}".format(
                name, " ".join(lacking)))
        drop = [p + "-" for p in (ALL_INIT_PACKAGES - set(packages)) | (LIVE_BACKENDS - {live}) if p in have]
        if init_id == "sysvinit":
            drop += [p + "-" for p in ("openrc", "runit-init") if p in have]
        # Removing the init system of a system is "essential" to APT: allow it for this one change.
        pk.chroot.run(APT + ["install", "--allow-remove-essential"] + want + drop)
    project.mark_initramfs_dirty()
    sync_services(project)
    wire_calamares(project, init_id)
    project.state.setdefault("init", {})["system"] = init_id
    project.save()
    project.record("init-system", init_id)
    log.info("Init system: %s", name)
    if current(r) != init_id:
        raise RuntimeError("{} was installed but the image still starts with {}".format(name, current(r)))
