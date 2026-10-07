"""All packages of the image's APT sources, read straight from /var/lib/apt/lists,
and the applications (.desktop files) that are installed in the image."""

import gzip
import lzma
import re
from pathlib import Path

from eduka_customizer.core.apt import is_installed_status, parse_deb822

# Debian sections that hold programs people start from the menu.
APP_SECTIONS = {"editors", "education", "electronics", "games", "gnome", "graphics", "hamradio", "kde",
                "mail", "math", "net", "news", "science", "sound", "text", "video", "web", "x11", "xfce",
                "comm", "database", "devel", "utils", "admin", "otherosfs", "tex", "misc"}
NOT_APPS = re.compile(r"^(lib|fonts-|python3?-|ruby-|perl-|node-|golang-|rust-|php-|r-cran-|haskell-|"
                      r"linux-(image|headers|modules)|firmware-)|(-dev|-dbg|-dbgsym|-doc|-data|-common|-l10n-.*|"
                      r"-help-.*|-dict-.*|-plugins?|-sounds|-textures|-music|-themes?|-fonts?|-icons?|-modules?|-bin|-tools-data)$")
# Never offered for removal: the system would not boot or install any more.
PROTECTED = {"live-boot", "live-config", "live-config-systemd", "linux-image-amd64", "systemd", "systemd-sysv",
             "dbus", "sudo", "apt", "dpkg", "network-manager", "grub-common", "plymouth", "calamares",
             "calamares-settings-debian", "policykit-1", "polkitd", "pkexec"}


def _open(path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", errors="replace")
    if path.suffix == ".xz":
        return lzma.open(path, "rt", errors="replace")
    return open(path, errors="replace")


def _stanzas(fh):
    """Fast reader for big Packages files: yields dicts with the fields we need."""
    cur = {}
    for line in fh:
        if line == "\n":
            if cur:
                yield cur
            cur = {}
            continue
        if line[0] in " \t":
            continue  # long description lines
        key, _, value = line.partition(":")
        if key in ("Package", "Version", "Section", "Installed-Size", "Description", "Priority",
                   "Essential", "Architecture"):
            cur[key] = value.strip()
    if cur:
        yield cur


def is_app(name, section):
    section = (section or "").split("/")[-1]
    return section in APP_SECTIONS and not NOT_APPS.search(name)


class Catalog:
    def __init__(self, rootfs):
        self.rootfs = Path(rootfs)

    def list_files(self):
        lists = self.rootfs / "var/lib/apt/lists"
        if not lists.is_dir():
            return []
        return sorted(p for p in lists.iterdir() if re.search(r"_Packages(\.gz|\.xz)?$", p.name))

    def available(self):
        """name -> {version, section, size (KiB), description, priority}."""
        out = {}
        for f in self.list_files():
            try:
                with _open(f) as fh:
                    for st in _stanzas(fh):
                        name = st.get("Package")
                        if not name or name in out:
                            continue
                        out[name] = {"version": st.get("Version", ""),
                                     "section": st.get("Section", "").split("/")[-1],
                                     "size": int(st.get("Installed-Size", "0") or 0),
                                     "description": st.get("Description", ""),
                                     "priority": st.get("Priority", ""),
                                     "essential": st.get("Essential", "") == "yes"}
            except (OSError, EOFError, lzma.LZMAError):
                continue
        return out

    def installed(self):
        status = self.rootfs / "var/lib/dpkg/status"
        out = {}
        if status.is_file():
            for st in parse_deb822(status.read_text(errors="replace")):
                if is_installed_status(st.get("Status", "")):
                    out[st.get("Package")] = {"version": st.get("Version", ""),
                                              "priority": st.get("Priority", ""),
                                              "essential": st.get("Essential", "") == "yes",
                                              "section": st.get("Section", "").split("/")[-1],
                                              "size": int(st.get("Installed-Size", "0") or 0),
                                              "description": st.get("Description", "").split("\n")[0]}
        return out

    def owners(self, paths):
        """Map file paths (as in the image, e.g. /usr/share/applications/x.desktop) to packages."""
        wanted = set(paths)
        out = {}
        info = self.rootfs / "var/lib/dpkg/info"
        if not info.is_dir() or not wanted:
            return out
        for lst in info.glob("*.list"):
            try:
                for line in lst.read_text(errors="replace").splitlines():
                    if line in wanted:
                        out[line] = lst.stem.split(":")[0]
            except OSError:
                continue
        return out

    def desktop_apps(self):
        """Installed applications: [{package, name, comment, desktop, protected}] sorted by name."""
        apps_dir = self.rootfs / "usr/share/applications"
        if not apps_dir.is_dir():
            return []
        entries = {}
        for f in sorted(apps_dir.glob("*.desktop")):
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            if re.search(r"(?m)^NoDisplay=true", text) or not re.search(r"(?m)^Type=Application", text):
                continue
            name = re.search(r"(?m)^Name=(.*)$", text)
            comment = re.search(r"(?m)^Comment=(.*)$", text)
            entries["/usr/share/applications/" + f.name] = (name.group(1) if name else f.stem,
                                                            comment.group(1) if comment else "")
        owners = self.owners(entries)
        installed = self.installed()
        by_pkg = {}
        for path, (name, comment) in entries.items():
            pkg = owners.get(path)
            if not pkg:
                continue
            info = installed.get(pkg, {})
            protected = pkg in PROTECTED or info.get("essential") or info.get("priority") in ("required",
                                                                                                 "important")
            by_pkg.setdefault(pkg, {"package": pkg, "names": [], "comment": comment, "protected": bool(protected),
                                    "size": info.get("size", 0)})["names"].append(name)
        apps = [dict(v, name=" / ".join(sorted(set(v["names"])))) for v in by_pkg.values()]
        return sorted(apps, key=lambda a: a["name"].lower())
