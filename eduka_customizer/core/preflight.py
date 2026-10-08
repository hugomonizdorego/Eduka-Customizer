"""Checks before building: everything that makes an ISO fail to build, fail to boot
or ship things it should not. Each check gives a level:

  ok    nothing to do
  info  good to know (for example what the build cleans up by itself)
  warn  the ISO builds, but look at it
  fail  the build would fail or the ISO would not work: fix it first
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from eduka_customizer.core import cleanup, distro, runner
from eduka_customizer.core.apt import parse_deb822
from eduka_customizer.core.chroot import mounts_under

LEVELS = ("ok", "info", "warn", "fail")
GIB = 1024 ** 3
# Typical xz squashfs ratio of a Debian desktop root filesystem.
SQUASH_RATIO = 0.38


@dataclass
class Result:
    level: str
    title: str
    detail: str = ""
    page: str = ""  # the page that fixes it

    def as_row(self):
        return (self.level, self.title, self.detail)


def tree_size(path):
    """Bytes used by a directory tree (one file system, hard links once)."""
    du = shutil.which("du")
    if du:
        try:
            out = runner.output([du, "-sxb", str(path)], quiet=True, check=False)
            return int(out.split()[0])
        except (ValueError, IndexError, OSError):
            pass
    total, seen = 0, set()
    for root, dirs, files in os.walk(path):
        for name in files:
            try:
                st = os.lstat(os.path.join(root, name))
            except OSError:
                continue
            if (st.st_dev, st.st_ino) in seen:
                continue
            seen.add((st.st_dev, st.st_ino))
            total += st.st_size
    return total


def _human(n):
    return "{:.1f} GiB".format(n / GIB) if n >= GIB else "{:.0f} MiB".format(n / 1024 ** 2)


def _dpkg_problems(rootfs):
    status = Path(rootfs, "var/lib/dpkg/status")
    if not status.is_file():
        return None
    bad = []
    for st in parse_deb822(status.read_text(errors="replace")):
        s = st.get("Status", "").split()
        if len(s) == 3 and s[2] not in ("installed", "not-installed", "config-files"):
            bad.append("{} ({})".format(st.get("Package"), s[2]))
        elif len(s) == 3 and s[1] == "reinstreq":
            bad.append("{} (reinstall required)".format(st.get("Package")))
    return bad


def _installed(rootfs):
    status = Path(rootfs, "var/lib/dpkg/status")
    if not status.is_file():
        return set()
    return {st.get("Package") for st in parse_deb822(status.read_text(errors="replace"))
            if st.get("Status", "").endswith(" ok installed")}


def run(project, deep=False):
    """All checks for *project*, in the order of the work. deep=True also runs apt-get check."""
    out = []
    add = lambda *a, **k: out.append(Result(*a, **k))  # noqa: E731
    p = project
    r = p.rootfs
    if not p.has_rootfs():
        add("fail", "No system in the project", "Extract an ISO, bootstrap Debian or snapshot this computer.",
            "ProjectPage")
        return out
    # 1. Distribution
    try:
        info = distro.detect(r)
        distro.validate(info, r)
        add("ok", "Distribution", info.summary())
    except distro.UnsupportedDistro as e:
        add("fail", "Distribution", str(e), "ProjectPage")
    # 2. Host tools
    missing = [t for t in ("mksquashfs", "xorriso") if not runner.which(t)]
    add("fail" if missing else "ok", "Build tools on this computer",
        "Missing: {} (sudo apt install squashfs-tools xorriso)".format(" ".join(missing)) if missing
        else "mksquashfs and xorriso found", "SettingsPage" if missing else "")
    # 3. Package database
    bad = _dpkg_problems(r)
    updates = Path(r, "var/lib/dpkg/updates")
    if bad is None:
        add("fail", "Package database", "/var/lib/dpkg/status is missing", "TerminalPage")
    elif bad or (updates.is_dir() and any(updates.iterdir())):
        detail = "Half-installed packages: " + ", ".join(bad[:8]) if bad else "An interrupted dpkg run was found"
        add("fail", "Package database", detail + ". Run 'dpkg --configure -a' and 'apt-get -f install' in the "
            "terminal (Advanced) or install/remove the packages again.", "TerminalPage")
    else:
        add("ok", "Package database", "every package is fully installed")
    if deep and bad == []:
        from eduka_customizer.core.chroot import Chroot
        try:
            text = Chroot(r).output(["apt-get", "check"], check=False)
            broken = "unmet" in (text or "").lower() or "broken" in (text or "").lower()
            add("fail" if broken else "ok", "Dependencies (apt-get check)",
                (text or "")[-400:] if broken else "no broken dependencies", "TerminalPage" if broken else "")
        except (OSError, RuntimeError) as e:
            add("warn", "Dependencies (apt-get check)", "could not run: {}".format(e))
    # 4. Kernel and live boot
    kernels = cleanup.kernels(r)
    if not kernels:
        add("warn", "Kernel", "No kernel in /boot: the build installs linux-image for you (needs internet).",
            "KernelPage")
    else:
        wanted = p.state.get("boot", {}).get("kernel")
        version = wanted if wanted in kernels else kernels[-1]
        if not Path(r, "boot/initrd.img-" + version).exists():
            add("warn", "Kernel", "initrd.img-{} is missing: the build creates it.".format(version), "KernelPage")
        else:
            add("ok", "Kernel", "{} with its initrd{}".format(version, " ({} kernels)".format(len(kernels))
                                                               if len(kernels) > 1 else ""))
    have = _installed(r)
    live_missing = [x for x in ("live-boot", "live-config", "live-config-systemd") if x not in have]
    add("warn" if live_missing else "ok", "Live boot support",
        "Missing {}: the build installs them (needs internet).".format(" ".join(live_missing)) if live_missing
        else "live-boot and live-config are installed", "PackagesPage" if live_missing else "")
    # 5. Desktop and login
    from eduka_customizer.core import desktop as dsk
    sessions = dsk.sessions(r)
    dm = dsk.detect_display_manager(r)
    chosen = p.state.get("desktop", {}).get("session")
    if dm and not sessions:
        add("fail", "Desktop", "A login screen ({}) is installed but no desktop session: nobody can log in."
            .format(dm), "DesktopPage")
    elif chosen and chosen not in {s["id"] for s in sessions}:
        add("warn", "Desktop", "The default session '{}' is not installed.".format(chosen), "DesktopPage")
    elif sessions:
        add("ok", "Desktop", "{} session(s){}".format(len(sessions), ", login screen " + dm if dm else ""))
    else:
        add("info", "Desktop", "No graphical desktop: the ISO boots to a text console.", "DesktopPage")
    # 6. Installer
    if "calamares" in have and not Path(r, "etc/calamares/settings.conf").is_file():
        add("warn", "Installer", "Calamares is installed without /etc/calamares/settings.conf.", "CalamaresPage")
    elif "calamares" in have:
        add("ok", "Installer", "Calamares is configured")
    else:
        add("info", "Installer", "No installer: the ISO only runs live.", "CalamaresPage")
    # 7. Identity
    if not p.state.get("identity", {}).get("name"):
        add("warn", "Identity", "No name was given: the ISO is called '{}'.".format(p.display_name()),
            "IdentityPage")
    else:
        add("ok", "Identity", "{} (ISO label {})".format(p.state["identity"]["name"], p.volume_label()))
    # 8. Boot menu edits
    try:
        from eduka_customizer.core import bootedit
        problems = []
        for key in bootedit.overrides(p):
            try:
                text = bootedit._store(p, "boot-overrides", key).read_text(errors="replace")
            except (OSError, ValueError):
                continue
            problems += ["{}: {}".format(key, x) for x in bootedit.validate(p, key, text)
                         if "copied there by the build" not in x]
        if problems:
            add("fail", "Edited boot menu", "; ".join(problems[:4]), "BootMenuPage")
        elif bootedit.overrides(p):
            add("ok", "Edited boot menu", "{} edited file(s) look fine".format(len(bootedit.overrides(p))))
    except ImportError:
        pass
    # 9. Leftovers of a crashed task
    left = mounts_under(r)
    if left:
        add("warn", "Mounts", "{} mount(s) are active inside the image; they are released before the build."
            .format(len(left)))
    if Path(r, "usr/sbin/policy-rc.d").exists():
        add("warn", "Services", "/usr/sbin/policy-rc.d is left in the image: services would not start in the "
            "live system. It is removed when the next task ends; remove it in the terminal if it stays.",
            "TerminalPage")
    # 10. Private data
    opts = p.state.get("build", {}).get("cleanup") or cleanup.defaults()
    notes = []
    mid = Path(r, "etc/machine-id")
    if mid.is_file() and mid.stat().st_size > 1:
        notes.append("machine-id")
    if list(Path(r, "etc/ssh").glob("ssh_host_*_key")):
        notes.append("SSH host keys")
    if notes:
        cleaned = all(opts.get(k, True) for k in ("machine_id", "ssh_keys"))
        add("info" if cleaned else "warn", "Private data", "{} {}".format(
            " and ".join(notes), "are removed by the build cleanup" if cleaned else
            "stay in the ISO: turn the cleanup options on (Check & Build)"))
    homes = [d for d in Path(r, "home").iterdir()] if Path(r, "home").is_dir() else []
    if homes:
        add("warn", "Private data", "/home has {}: everything there ends up in the ISO."
            .format(", ".join(sorted(d.name for d in homes)[:5])), "UsersPage")
    # 11. Space
    size = tree_size(r)
    iso = int(size * SQUASH_RATIO) + 64 * 1024 ** 2
    free = shutil.disk_usage(p.path).free
    need = iso + GIB
    add("fail" if free < need else "ok", "Free disk space",
        "{} free, about {} needed".format(_human(free), _human(need)))
    add("warn" if iso > 4 * GIB else "info", "ISO size",
        "about {} (system {}){}".format(_human(iso), _human(size),
                                        ": larger than a DVD, use a USB stick" if iso > 4.4 * GIB else ""))
    return out


def summary(results):
    """(fails, warnings) counts."""
    return (sum(1 for x in results if x.level == "fail"), sum(1 for x in results if x.level == "warn"))
