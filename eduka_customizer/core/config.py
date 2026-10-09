"""Global settings (/etc/distroforge/distroforge.conf)."""

import configparser
import os
from pathlib import Path

# Default time zone (Timor-Leste); every project can choose another one.
DEFAULT_TIMEZONE = "Asia/Dili"
CONFIG_PATH = Path(os.environ.get("DISTROFORGE_CONF") or os.environ.get("EDUKA_CUSTOMIZER_CONF") or
                   "/etc/distroforge/distroforge.conf")
# Settings of the versions called Eduka-Customizer are read when there are no new ones yet.
OLD_CONFIG_PATH = Path("/etc/eduka-customizer/eduka-customizer.conf")

# Directory holding exclude.list, desktops.json, templates, ...
DATA_DIR = Path(os.environ.get("DISTROFORGE_DATA") or os.environ.get("EDUKA_CUSTOMIZER_DATA") or
                "/usr/share/distroforge")
_SOURCE_DATA = Path(__file__).resolve().parents[2] / "data"

DEFAULTS = {
    "general": {
        "projects_dir": "/home/distroforge",
        "recent_projects": "",
        "theme": "auto",
        "terminal": "",
        # yes: every menu can be opened at any time (expert mode); no: one step after the other.
        "free_navigation": "no",
        # review: changes wait in Review & Apply (recommended); now: every change is applied at once.
        "apply_mode": "review",
    },
    "debian": {
        # Codenames change with every Debian release; update them here.
        "oldstable": "bookworm",
        "stable": "trixie",
        "testing": "forky",
        "allow_oldstable": "no",
        "mirror": "http://deb.debian.org/debian",
        "security_mirror": "http://security.debian.org/debian-security",
        "components": "main contrib non-free non-free-firmware",
        "live_iso_url": "https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/",
        "testing_live_iso_url": "https://cdimage.debian.org/cdimage/weekly-live-builds/amd64/iso-hybrid/",
    },
    # Eduka-Desktop is one of the desktops on offer; nothing else about a distribution is preset.
    "eduka_desktop": {
        "repo": "https://github.com/hugomonizdorego/Eduka-Desktop",
        "ref": "",
    },
    "flatpak": {
        "remote_name": "flathub",
        "remote_url": "https://dl.flathub.org/repo/flathub.flatpakrepo",
        "api_url": "https://flathub.org/api/v2",
    },
    "build": {
        "compression": "zstd",
        "compression_level": "15",
        "block_size": "1M",
        "iso_name": "{id}-{version}-{suite}-{arch}-{date}.iso",
        "checksums": "sha256",
    },
    "qemu": {
        "memory": "4096",
        "cpus": "2",
        "firmware": "uefi",
        "disk_size": "32G",
    },
}


class Settings:
    def __init__(self, path=CONFIG_PATH):
        self.path = Path(path)
        self.parser = configparser.ConfigParser(interpolation=None)
        self.parser.read_dict(DEFAULTS)
        if self.path.is_file():
            self.parser.read(self.path, encoding="utf-8")
        elif self.path == CONFIG_PATH and OLD_CONFIG_PATH.is_file():
            self.parser.read(OLD_CONFIG_PATH, encoding="utf-8")
        # Settings of versions before 0.15 called the Eduka-Desktop section [edukasaun].
        if self.parser.has_section("edukasaun"):
            for key in ("repo", "ref"):
                old = self.parser.get("edukasaun", key, fallback="")
                if old and self.parser.get("eduka_desktop", key) == DEFAULTS["eduka_desktop"][key]:
                    self.parser.set("eduka_desktop", key, old)

    def get(self, section, key):
        return self.parser.get(section, key, fallback=DEFAULTS.get(section, {}).get(key, ""))

    def getbool(self, section, key):
        return self.parser.getboolean(section, key, fallback=False)

    def getint(self, section, key):
        try:
            return int(self.get(section, key))
        except ValueError:
            return int(DEFAULTS[section][key])

    def set(self, section, key, value):
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, key, str(value))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("# DistroForge settings. Edited by the GUI as well.\n")
            self.parser.write(fh)
        os.replace(tmp, self.path)

    # Recent projects -------------------------------------------------
    def recent_projects(self):
        items = [p for p in self.get("general", "recent_projects").split(":") if p]
        return [p for p in items if Path(p, "project.json").is_file()]

    def add_recent(self, path):
        items = [str(path)] + [p for p in self.recent_projects() if p != str(path)]
        self.set("general", "recent_projects", ":".join(items[:10]))
        try:
            self.save()
        except OSError:
            pass

    # Debian release names -------------------------------------------
    def suite_codenames(self):
        return {
            "oldstable": self.get("debian", "oldstable"),
            "stable": self.get("debian", "stable"),
            "testing": self.get("debian", "testing"),
            "sid": "sid",
        }


def data_file(*parts):
    """Locate a data file, preferring the installed copy."""
    for base in (DATA_DIR, _SOURCE_DATA):
        p = base.joinpath(*parts)
        if p.exists():
            return p
    return DATA_DIR.joinpath(*parts)


_settings = None


def settings():
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload():
    global _settings
    _settings = Settings()
    return _settings
