"""Detect and validate the distribution inside a root filesystem.

Debian (stable, testing, sid) and every Debian-based distribution are accepted.
Ubuntu and every Ubuntu derivative is rejected on purpose.
"""

import re
import struct
from dataclasses import asdict, dataclass, field
from pathlib import Path

from eduka_customizer.core.config import settings

ALLOWED_IDS = ("debian", "edukasaun")
# Ubuntu and systems built on it. Linux Mint is only refused when it is Ubuntu-based:
# Linux Mint Debian Edition (LMDE, ID_LIKE=debian) is a Debian derivative and welcome.
UBUNTU_MARKERS = ("ubuntu", "pop", "elementary", "zorin", "neon",
                  "kubuntu", "xubuntu", "lubuntu", "tuxedo")

# Debian major version -> codename (used when /etc/debian_version is numeric).
DEBIAN_MAJOR = {"11": "bullseye", "12": "bookworm", "13": "trixie",
                "14": "forky", "15": "duke"}

ELF_MACHINES = {0x3E: "amd64", 0x03: "i386", 0xB7: "arm64", 0x28: "armhf",
                0xF3: "riscv64", 0x15: "ppc64el"}


class UnsupportedDistro(Exception):
    pass


@dataclass
class DistroInfo:
    id: str = ""
    id_like: list = field(default_factory=list)
    name: str = ""
    pretty_name: str = ""
    version_id: str = ""
    codename: str = ""
    debian_version: str = ""
    debian_codename: str = ""
    suite: str = "unknown"
    arch: str = ""
    is_edukasaun: bool = False
    apt_suites: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def summary(self):
        label = {"stable": "Debian stable", "testing": "Debian testing",
                 "sid": "Debian sid (unstable)", "oldstable": "Debian oldstable"}.get(self.suite, self.suite)
        base = "{} ({})".format(label, self.debian_codename or "?")
        if self.id and self.id != "debian":
            # Any derivative (Edukasaun OS, LMDE, your own distribution): show its Debian base too.
            return "{} - based on {} - {}".format(self.pretty_name or self.name or self.id, base, self.arch)
        return "{} - {}".format(self.pretty_name or base, self.arch)


def parse_os_release(text):
    data = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        value = re.sub(r"\\(.)", r"\1", value)
        data[key.strip()] = value
    return data


def format_os_release(data):
    lines = []
    for key, value in data.items():
        value = str(value)
        if re.fullmatch(r"[A-Za-z0-9._-]*", value):
            lines.append("{}={}".format(key, value))
        else:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
            lines.append('{}="{}"'.format(key, escaped))
    return "\n".join(lines) + "\n"


def read_os_release(rootfs):
    rootfs = Path(rootfs)
    for rel in ("etc/os-release", "usr/lib/os-release"):
        p = resolve_in_root(rootfs, rel)
        if p and p.is_file():
            return parse_os_release(p.read_text(errors="replace"))
    return {}


def resolve_in_root(rootfs, rel):
    """Resolve *rel* inside rootfs, following symlinks relative to rootfs."""
    rootfs = Path(rootfs)
    parts = [p for p in Path(rel).parts if p not in ("/", "")]
    current = rootfs
    for _ in range(40):
        if not parts:
            return current
        name = parts.pop(0)
        candidate = current / name
        if candidate.is_symlink():
            target = Path(str(candidate.readlink()))
            if target.is_absolute():
                current = rootfs
                parts = list(target.parts[1:]) + parts
            else:
                parts = list(target.parts) + parts
            continue
        if name == "..":
            current = current.parent if current != rootfs else rootfs
            continue
        current = candidate
    return None


def apt_suites(rootfs):
    """Return the suites configured in the root filesystem's APT sources."""
    rootfs = Path(rootfs)
    suites = []
    files = [rootfs / "etc/apt/sources.list"]
    d = rootfs / "etc/apt/sources.list.d"
    if d.is_dir():
        files += sorted(d.glob("*.list")) + sorted(d.glob("*.sources"))
    for f in files:
        if not f.is_file():
            continue
        text = f.read_text(errors="replace")
        if f.suffix == ".sources":
            uri_ok = False
            for stanza in re.split(r"\n\s*\n", text):
                if re.search(r"(?im)^Enabled:\s*no\b", stanza):
                    continue
                uris = re.search(r"(?im)^URIs:\s*(.+)$", stanza)
                m = re.search(r"(?im)^Suites:\s*(.+)$", stanza)
                uri_ok = bool(uris and "debian" in uris.group(1))
                if m and uri_ok:
                    suites += m.group(1).split()
        else:
            for line in text.splitlines():
                line = line.split("#", 1)[0].strip()
                if not line.startswith(("deb ", "deb-src ")):
                    continue
                tokens = re.sub(r"\[[^\]]*\]", "", line).split()
                if len(tokens) >= 3 and "debian" in tokens[1]:
                    suites.append(tokens[2])
    return suites


def detect_suite(debian_codename, debian_version, suites, codenames=None):
    codenames = codenames or settings().suite_codenames()
    base = {s.split("-")[0].split("/")[0] for s in suites}
    if base & {"sid", "unstable"}:
        return "sid"
    if base & {"testing", codenames["testing"]}:
        return "testing"
    if base & {"stable", codenames["stable"]}:
        return "stable"
    if base & {"oldstable", codenames["oldstable"]}:
        return "oldstable"
    # No usable APT data: fall back to /etc/debian_version.
    if "/sid" in debian_version or debian_version.strip() == "sid":
        return "testing" if debian_codename == codenames["testing"] else "sid"
    for name, code in codenames.items():
        if debian_codename == code:
            return name
    return "unknown"


def elf_arch(rootfs):
    for rel in ("usr/bin/dpkg", "bin/sh", "usr/bin/env"):
        p = resolve_in_root(rootfs, rel)
        if not p or not p.is_file():
            continue
        try:
            with open(p, "rb") as fh:
                head = fh.read(20)
        except OSError:
            continue
        if head[:4] != b"\x7fELF":
            continue
        endian = "<" if head[5] == 1 else ">"
        machine = struct.unpack(endian + "H", head[18:20])[0]
        if machine == 0x03 or machine == 0x3E:
            return "amd64" if head[4] == 2 else "i386"
        return ELF_MACHINES.get(machine, "unknown")
    return ""


def detect(rootfs):
    rootfs = Path(rootfs)
    osr = read_os_release(rootfs)
    info = DistroInfo()
    info.id = osr.get("ID", "").lower()
    info.id_like = osr.get("ID_LIKE", "").lower().split()
    info.name = osr.get("NAME", "")
    info.pretty_name = osr.get("PRETTY_NAME", "")
    info.version_id = osr.get("VERSION_ID", "")
    info.codename = osr.get("VERSION_CODENAME", "")
    dv = resolve_in_root(rootfs, "etc/debian_version")
    info.debian_version = dv.read_text(errors="replace").strip() if dv and dv.is_file() else ""
    info.apt_suites = apt_suites(rootfs)

    codenames = settings().suite_codenames()
    major = info.debian_version.split(".")[0]
    if major in DEBIAN_MAJOR:
        info.debian_codename = DEBIAN_MAJOR[major]
    elif "/" in info.debian_version:
        info.debian_codename = info.debian_version.split("/")[0]
    elif info.id == "debian" and info.codename:
        info.debian_codename = info.codename
    suite_codes = {s.split("-")[0] for s in info.apt_suites}
    if not info.debian_codename:
        for code in codenames.values():
            if code in suite_codes:
                info.debian_codename = code
                break
    info.suite = detect_suite(info.debian_codename, info.debian_version, info.apt_suites, codenames)
    if info.suite == "sid":
        info.debian_codename = "sid"
    info.is_edukasaun = (info.id == "edukasaun" or "edukasaun" in info.name.lower()
                         or "edukasaun" in info.pretty_name.lower())
    info.arch = elf_arch(rootfs)
    return info


def validate(info, rootfs=None):
    """Raise UnsupportedDistro unless this is Debian or a Debian derivative."""
    ids = [info.id] + list(info.id_like)
    if any(m in ids for m in UBUNTU_MARKERS) or "ubuntu" in info.name.lower() \
            or "ubuntu" in info.pretty_name.lower() or (info.id == "linuxmint" and "debian" not in info.id_like):
        raise UnsupportedDistro(
            "Ubuntu and Ubuntu-based systems are not supported. DistroForge "
            "builds Debian-based distributions (Debian stable, testing, sid and derivatives).")
    if rootfs is not None:
        lsb = Path(rootfs, "etc/lsb-release")
        if lsb.is_file() and "ubuntu" in lsb.read_text(errors="replace").lower():
            raise UnsupportedDistro("This filesystem identifies itself as Ubuntu (/etc/lsb-release).")
    if not info.debian_version:
        raise UnsupportedDistro("/etc/debian_version is missing: this is not a Debian system.")
    if info.id not in ALLOWED_IDS and not info.is_edukasaun and "debian" not in info.id_like:
        raise UnsupportedDistro(
            "'{}' is not supported. Debian and Debian derivatives (such as LMDE) "
            "can be customized.".format(info.pretty_name or info.id or "Unknown system"))
    if info.suite == "oldstable" and not settings().getbool("debian", "allow_oldstable"):
        raise UnsupportedDistro(
            "Debian oldstable ({}) is not supported. Upgrade the base to stable, testing or sid "
            "first, or set allow_oldstable=yes in the settings.".format(info.debian_codename))
    if info.suite == "unknown":
        raise UnsupportedDistro(
            "Could not determine the Debian suite (debian_version '{}'). Supported: "
            "stable, testing and sid.".format(info.debian_version))
    return True
