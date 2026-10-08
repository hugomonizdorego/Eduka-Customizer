"""Replace the default applications of a desktop (browser, mail, office, editor, file
manager, terminal, viewers, players, ...) with the programs you prefer.

The new program is installed, made the default for its file types
(/etc/xdg/mimeapps.list) and for its Debian alternatives (x-www-browser,
x-terminal-emulator, ...), and the old programs can be removed. Removing never
takes the desktop with it: see Packages.keep_desktop.
"""

import configparser
import json
import re
from pathlib import Path

from eduka_customizer.core.apt import Packages, is_installed_status, parse_deb822
from eduka_customizer.core.config import data_file
from eduka_customizer.core.log import log

MIMEAPPS = "etc/xdg/mimeapps.list"


def roles():
    with open(data_file("apps.json"), encoding="utf-8") as fh:
        return json.load(fh)["roles"]


def role(role_id):
    for r in roles():
        if r["id"] == role_id:
            return r
    raise KeyError("Unknown kind of application: {} (use {})".format(role_id, ", ".join(x["id"] for x in roles())))


def _installed(rootfs):
    status = Path(rootfs, "var/lib/dpkg/status")
    if not status.is_file():
        return set()
    return {st.get("Package") for st in parse_deb822(status.read_text(errors="replace"))
            if is_installed_status(st.get("Status", ""))}


def package_files(rootfs, package):
    """Files of an installed package, from /var/lib/dpkg/info."""
    info = Path(rootfs, "var/lib/dpkg/info")
    for name in [package + ".list"] + sorted(p.name for p in info.glob(package + ":*.list")) if info.is_dir() else []:
        f = info / name
        if f.is_file():
            return [line for line in f.read_text(errors="replace").splitlines() if line]
    return []


def desktop_ids(rootfs, package, mimes=()):
    """The .desktop file names a package ships; those that open *mimes* first."""
    out = []
    for path in package_files(rootfs, package):
        if re.match(r"^/usr/share/applications/[^/]+\.desktop$", path):
            name = path.rsplit("/", 1)[1]
            text = ""
            try:
                text = Path(rootfs, path.lstrip("/")).read_text(errors="replace")
            except OSError:
                pass
            if re.search(r"(?m)^NoDisplay=true", text):
                continue
            m = re.search(r"(?m)^MimeType=(.*)$", text)
            types = set(m.group(1).split(";")) if m else set()
            out.append((0 if types & set(mimes) else 1, name))
    return [n for _k, n in sorted(out)]


def read_defaults(rootfs):
    p = Path(rootfs, MIMEAPPS)
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    cp.optionxform = str
    if p.is_file():
        try:
            cp.read(p, encoding="utf-8")
        except configparser.Error:
            pass
    return dict(cp["Default Applications"]) if cp.has_section("Default Applications") else {}


def status(rootfs):
    """[{role, name, installed: [packages], default: desktop id, candidates: [packages]}]."""
    have = _installed(rootfs)
    defaults = read_defaults(rootfs)
    out = []
    for r in roles():
        default = ""
        for m in r["mime"]:
            if defaults.get(m):
                default = defaults[m].split(";")[0]
                break
        out.append({"role": r["id"], "name": r["name"], "installed": [c for c in r["candidates"] if c in have],
                    "default": default, "candidates": list(r["candidates"])})
    return out


def write_defaults(rootfs, mimes, desktop_id):
    """Make *desktop_id* the default for *mimes* in /etc/xdg/mimeapps.list (and in the
    desktop-specific lists that already exist there, which would win otherwise)."""
    files = [Path(rootfs, MIMEAPPS)] + sorted(Path(rootfs, "etc/xdg").glob("*-mimeapps.list"))
    for p in files:
        cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
        cp.optionxform = str
        if p.is_file():
            try:
                cp.read(p, encoding="utf-8")
            except configparser.Error:
                pass
        elif p.name != "mimeapps.list":
            continue
        if not cp.has_section("Default Applications"):
            cp.add_section("Default Applications")
        for m in mimes:
            cp.set("Default Applications", m, desktop_id + ";")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            cp.write(fh, space_around_delimiters=False)


def alternative_paths(rootfs, name):
    """Paths registered for a Debian alternative (from /var/lib/dpkg/alternatives/<name>).

    The file is: mode, master link, (slave name, slave link) pairs, an empty line,
    then per choice its path, priority and one line per slave; an empty path ends it."""
    f = Path(rootfs, "var/lib/dpkg/alternatives", name)
    if not f.is_file():
        return []
    lines = f.read_text(errors="replace").split("\n")
    i, slaves = 2, 0
    while i < len(lines) and lines[i]:
        slaves += 1
        i += 2
    i += 1
    out = []
    while i < len(lines) and lines[i]:
        out.append(lines[i])
        i += 2 + slaves
    return out


class Replacer:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.pkgs = Packages(project)

    def replace(self, role_id, new, remove=(), progress=None):
        """Install *new* as the default *role_id* application and remove *remove*."""
        r = role(role_id)
        remove = [p for p in remove if p and p != new]
        with self.pkgs.chroot:
            if new not in _installed(self.rootfs):
                if progress:
                    progress("Installing " + new)
                self.pkgs.install([new])
            self.set_default(r, new)
            if remove:
                if progress:
                    progress("Removing " + " ".join(remove))
                self.pkgs.remove(remove)
        self.project.state.setdefault("default_apps", {})[role_id] = new
        self.project.save()
        self.project.record("replace-app", "{}: {}{}".format(role_id, new,
                                                              " (removed {})".format(" ".join(remove)) if remove else ""))

    def set_default(self, r, package):
        files = set(package_files(self.rootfs, package))
        ids = desktop_ids(self.rootfs, package, r["mime"])
        if r["mime"]:
            if ids:
                write_defaults(self.rootfs, r["mime"], ids[0])
                log.info("Default %s: %s", r["name"].lower(), ids[0])
            else:
                log.warning("%s has no menu entry: file types are left as they are", package)
        for alt in r.get("alternatives", []):
            for path in alternative_paths(self.rootfs, alt):
                if path in files:
                    self.pkgs.chroot.run(["update-alternatives", "--set", alt, path], check=False, quiet=True)
                    log.info("Alternative %s: %s", alt, path)
                    break
