"""Global settings (/etc/eduka-customizer/eduka-customizer.conf)."""

import configparser
import os
from pathlib import Path

# Edukasaun OS is made for Timor-Leste: the default time zone everywhere.
DEFAULT_TIMEZONE = "Asia/Dili"
CONFIG_PATH = Path(os.environ.get("EDUKA_CUSTOMIZER_CONF",
                                  "/etc/eduka-customizer/eduka-customizer.conf"))

# Directory holding exclude.list, desktops.json, templates, ...
DATA_DIR = Path(os.environ.get("EDUKA_CUSTOMIZER_DATA", "/usr/share/eduka-customizer"))
_SOURCE_DATA = Path(__file__).resolve().parents[2] / "data"

DEFAULTS = {
    "general": {
        "projects_dir": "/home/eduka-customizer",
        "recent_projects": "",
        "theme": "auto",
        "terminal": "",
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
    "edukasaun": {
        "name": "Edukasaun OS",
        "id": "edukasaun",
        "version": "1.0",
        "codename": "Kameli",
        "home_url": "https://edukasaun.org",
        "eduka_desktop_repo": "https://github.com/hugomonizdorego/Eduka-Desktop",
        "eduka_desktop_ref": "",
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
            fh.write("# Eduka-Customizer settings. Edited by the GUI as well.\n")
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
