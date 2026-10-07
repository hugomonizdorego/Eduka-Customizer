"""APT sources and package management inside the root filesystem."""

import re
import shutil
import urllib.request
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.config import settings
from eduka_customizer.core.log import log

KEYRING = "/usr/share/keyrings/debian-archive-keyring.gpg"
SOURCES_DIR = "etc/apt/sources.list.d"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


# --------------------------------------------------------------------------
# deb822 helpers

def parse_deb822(text):
    """Parse a deb822 file into a list of {field: value} stanzas."""
    stanzas, current, last = [], {}, None
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        if not line.strip():
            if current:
                stanzas.append(current)
            current, last = {}, None
            continue
        if line[0] in " \t" and last:
            current[last] += "\n" + line.strip()
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            last = key.strip()
            current[last] = value.strip()
    if current:
        stanzas.append(current)
    return stanzas


def format_deb822(stanzas):
    blocks = []
    for st in stanzas:
        lines = []
        for key, value in st.items():
            value = str(value)
            if "\n" in value:
                first, *rest = value.split("\n")
                lines.append("{}: {}".format(key, first))
                lines.extend(" " + (r if r.strip() else ".") for r in rest)
            else:
                lines.append("{}: {}".format(key, value))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def oneline_to_deb822(text):
    """Convert classic sources.list lines into deb822 stanzas."""
    stanzas = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        m = re.match(r"^(deb|deb-src)\s+(?:\[([^\]]*)\]\s+)?(\S+)\s+(\S+)\s*(.*)$", line)
        if not m:
            continue
        kind, opts, uri, suite, comps = m.groups()
        st = {"Types": kind, "URIs": uri, "Suites": suite}
        if comps:
            st["Components"] = comps
        for opt in (opts or "").split():
            if "=" in opt:
                k, v = opt.split("=", 1)
                key = {"signed-by": "Signed-By", "arch": "Architectures",
                       "trusted": "Trusted"}.get(k.lower(), k)
                st[key] = v.replace(",", " ")
        stanzas.append(st)
    return stanzas


def debian_sources(suite, mirror=None, security_mirror=None, components=None,
                   updates=True, security=True, backports=False, deb_src=False,
                   use_codename=True):
    """Build the stanzas of a standard debian.sources file."""
    cfg = settings()
    codes = cfg.suite_codenames()
    mirror = mirror or cfg.get("debian", "mirror")
    security_mirror = security_mirror or cfg.get("debian", "security_mirror")
    components = components or cfg.get("debian", "components")
    if suite not in ("stable", "testing", "sid", "oldstable"):
        raise ValueError("Unsupported suite: {}".format(suite))
    name = (codes[suite] if use_codename else suite) if suite != "sid" else "sid"
    types = "deb deb-src" if deb_src else "deb"
    suites = [name]
    if suite != "sid" and updates:
        suites.append(name + "-updates")
    if suite == "stable" and backports:
        suites.append(name + "-backports")
    stanzas = [{"Types": types, "URIs": mirror, "Suites": " ".join(suites),
                "Components": components, "Signed-By": KEYRING}]
    if suite != "sid" and security:
        stanzas.append({"Types": types, "URIs": security_mirror,
                        "Suites": name + "-security", "Components": components,
                        "Signed-By": KEYRING})
    return stanzas


# --------------------------------------------------------------------------
# Source file management

class Sources:
    def __init__(self, rootfs):
        self.rootfs = Path(rootfs)

    @property
    def dir(self):
        return self.rootfs / SOURCES_DIR

    def files(self):
        result = []
        legacy = self.rootfs / "etc/apt/sources.list"
        if legacy.exists():
            result.append(legacy)
        if self.dir.is_dir():
            result += sorted(p for p in self.dir.iterdir()
                             if p.suffix in (".list", ".sources") and p.is_file())
        return result

    def path_for(self, name):
        if "/" in str(name):
            raise ValueError("Invalid sources file name: {}".format(name))
        if name == "sources.list":
            return self.rootfs / "etc/apt/sources.list"
        if not SAFE_NAME.match(name) or not name.endswith((".list", ".sources")):
            raise ValueError("Invalid sources file name: {}".format(name))
        return self.dir / name

    def read(self, name):
        p = self.path_for(name)
        return p.read_text(errors="replace") if p.exists() else ""

    def write(self, name, text):
        p = self.path_for(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".sources":
            for st in parse_deb822(text):
                missing = [k for k in ("Types", "URIs", "Suites") if k not in st]
                if missing and st.get("Enabled", "yes").lower() != "no":
                    raise ValueError("{}: stanza is missing {}".format(name, ", ".join(missing)))
        p.write_text(text if text.endswith("\n") else text + "\n")
        log.info("Saved %s", p.relative_to(self.rootfs))

    def delete(self, name):
        p = self.path_for(name)
        if p.exists():
            p.unlink()
            log.info("Removed %s", p.relative_to(self.rootfs))

    def set_debian(self, suite, **kw):
        """Replace the Debian entries with a clean deb822 debian.sources."""
        stanzas = debian_sources(suite, **kw)
        legacy = self.rootfs / "etc/apt/sources.list"
        if legacy.exists() and re.search(r"(?m)^\s*deb\s", legacy.read_text(errors="replace")):
            shutil.move(str(legacy), str(legacy) + ".eduka-old")
            legacy.write_text("# Moved to /etc/apt/sources.list.d/debian.sources by Eduka-Customizer\n")
        for p in self.files():
            if p.suffix == ".sources" and p.name != "debian.sources":
                stz = parse_deb822(p.read_text(errors="replace"))
                if stz and all("deb.debian.org" in s.get("URIs", "") or
                               "security.debian.org" in s.get("URIs", "") for s in stz):
                    p.rename(p.with_name(p.name + ".eduka-old"))
        self.write("debian.sources", format_deb822(stanzas))
        return stanzas

    def add_repository(self, name, uri, suites, components="main", key=None, arch=None):
        """Add a third-party repository with its own keyring (Signed-By)."""
        if not SAFE_NAME.match(name):
            raise ValueError("Repository name may contain letters, digits, '.', '_' and '-'")
        stanza = {"Types": "deb", "URIs": uri, "Suites": suites}
        if components:
            stanza["Components"] = components
        if arch:
            stanza["Architectures"] = arch
        if key:
            keyring = self.install_key(name, key)
            stanza["Signed-By"] = "/" + str(keyring.relative_to(self.rootfs))
        self.write(name + ".sources", format_deb822([stanza]))

    def install_key(self, name, key):
        """Store a repository key (URL or local file, armored or binary)."""
        if re.match(r"^https?://", key):
            log.info("Downloading key %s", key)
            req = urllib.request.Request(key, headers={"User-Agent": "Eduka-Customizer"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
        else:
            data = Path(key).read_bytes()
        dest = self.rootfs / "etc/apt/keyrings" / (name + ".gpg")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if b"-----BEGIN PGP PUBLIC KEY BLOCK-----" in data:
            if runner.which("gpg"):
                runner.run(["gpg", "--batch", "--yes", "--dearmor", "-o", dest], input=data)
            else:
                dest = dest.with_suffix(".asc")
                dest.write_bytes(data)
        else:
            dest.write_bytes(data)
        dest.chmod(0o644)
        return dest


# --------------------------------------------------------------------------
# Package operations

APT = ["apt-get", "-y", "-o", "Dpkg::Options::=--force-confdef",
       "-o", "Dpkg::Options::=--force-confold", "-o", "APT::Color=0",
       "-o", "Dpkg::Progress-Fancy=0"]
_PKG = re.compile(r"^[a-z0-9][a-z0-9+.\-]*(:[a-z0-9]+)?([=/][A-Za-z0-9.+~:\-]+)?$")


def _check_names(packages):
    bad = [p for p in packages if not _PKG.match(p)]
    if bad:
        raise ValueError("Invalid package name(s): {}".format(", ".join(bad)))


class Packages:
    def __init__(self, project):
        self.project = project
        self.chroot = Chroot(project.rootfs)

    def update(self):
        log.info("Updating package lists")
        self.chroot.run(APT + ["update"])

    def upgrade(self):
        log.info("Upgrading all packages (full-upgrade)")
        with self.chroot:
            self.update()
            self.chroot.run(APT + ["full-upgrade"])
        self.project.mark_initramfs_dirty()
        self.project.record("apt-upgrade")

    def install(self, packages, no_recommends=False, update=True):
        packages = [p for p in packages if p]
        if not packages:
            return
        _check_names(packages)
        log.info("Installing: %s", " ".join(packages))
        with self.chroot:
            if update:
                self.update()
            extra = ["--no-install-recommends"] if no_recommends else []
            self.chroot.run(APT + ["install"] + extra + packages)
        self.project.mark_initramfs_dirty()
        self.project.record("apt-install", " ".join(packages))

    def remove(self, packages, purge=True, autoremove=True):
        packages = [p for p in packages if p]
        if not packages:
            return
        _check_names(packages)
        log.info("Removing: %s", " ".join(packages))
        with self.chroot:
            self.chroot.run(APT + (["purge"] if purge else ["remove"]) + packages)
            if autoremove:
                self.chroot.run(APT + ["autoremove", "--purge"])
        self.project.record("apt-remove", " ".join(packages))

    def autoremove(self):
        self.chroot.run(APT + ["autoremove", "--purge"])

    def clean(self):
        self.chroot.run(APT + ["clean"])

    def install_debs(self, files):
        """Install local .deb files, resolving their dependencies with APT."""
        files = [Path(f) for f in files]
        tmp = self.project.rootfs / "tmp/eduka-debs"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            inside = []
            for f in files:
                if f.suffix != ".deb" or not f.is_file():
                    raise ValueError("Not a .deb file: {}".format(f))
                shutil.copy2(f, tmp / f.name)
                inside.append("/tmp/eduka-debs/" + f.name)
            with self.chroot:
                self.update()
                self.chroot.run(APT + ["install"] + inside)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.project.mark_initramfs_dirty()
        self.project.record("deb-install", " ".join(f.name for f in files))

    def search(self, term, limit=300):
        if not term.strip():
            return []
        out = self.chroot.output(["apt-cache", "search", "--", term], check=False)
        results = []
        for line in out.splitlines()[:limit]:
            name, _, desc = line.partition(" - ")
            results.append((name.strip(), desc.strip()))
        return results

    def show(self, name):
        _check_names([name])
        return self.chroot.output(["apt-cache", "show", "--no-all-versions", name], check=False)

    def installed(self):
        """Read the dpkg status database directly (no chroot required)."""
        status = self.project.rootfs / "var/lib/dpkg/status"
        result = []
        if not status.is_file():
            return result
        for st in parse_deb822(status.read_text(errors="replace")):
            if "install ok installed" in st.get("Status", ""):
                result.append((st.get("Package", ""), st.get("Version", ""),
                               st.get("Installed-Size", "0"),
                               st.get("Description", "").split("\n")[0]))
        return sorted(result)

    def is_installed(self, name):
        return any(p[0] == name for p in self.installed())


def read_package_list(path):
    """Read a package list file: one name per line, '#' comments, '-name' removes."""
    install, remove = [], []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        for token in line.split():
            (remove if token.startswith("-") else install).append(token.lstrip("-"))
    return install, remove
