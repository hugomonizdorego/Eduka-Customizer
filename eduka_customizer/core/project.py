"""A customization project: work directories plus persistent state."""

import datetime
import fcntl
import json
import os
from pathlib import Path

from eduka_customizer import VERSION
from eduka_customizer.core.config import DEFAULT_TIMEZONE
from eduka_customizer.core.distro import DistroInfo

STATE_FILE = "project.json"

DEFAULT_STATE = {
    "format": 1,
    "name": "Edukasaun OS",
    "created": "",
    "customizer_version": VERSION,
    "source": {"kind": "", "path": "", "label": "", "boot_mode": "replay"},
    "distro": {},
    "identity": {
        "name": "Edukasaun OS",
        "id": "edukasaun",
        "version": "1.0",
        "codename": "Kameli",
        "home_url": "https://edukasaun.org",
        "support_url": "",
        "bug_url": "",
        "hostname": "edukasaun",
        "live_user": "eduka",
        "live_fullname": "Edukasaun Live User",
        "volume_label": "EDUKASAUN_OS",
    },
    "locale": {"default": "en_US.UTF-8", "extra": ["pt_PT.UTF-8", "id_ID.UTF-8"],
               "timezone": DEFAULT_TIMEZONE, "keyboard": "us"},
    "build": {},
    "boot": {"extra_params": "quiet splash", "timeout": 10, "title": ""},
    "flatpak": {"firstboot": []},
    "history": [],
    "last_iso": "",
    "initramfs_dirty": False,
}


class ProjectLocked(RuntimeError):
    pass


class Project:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.state = json.loads(json.dumps(DEFAULT_STATE))
        self._lock_fh = None

    # Paths -----------------------------------------------------------
    @property
    def rootfs(self):
        return self.path / "rootfs"

    @property
    def isodir(self):
        return self.path / "iso"

    @property
    def output(self):
        return self.path / "output"

    @property
    def cache(self):
        return self.path / "cache"

    @property
    def bootdir(self):
        """Boot images extracted from the source ISO (MBR, EFI partition)."""
        return self.path / "boot"

    @property
    def logs(self):
        return self.path / "logs"

    @property
    def state_file(self):
        return self.path / STATE_FILE

    # Life cycle --------------------------------------------------------
    @classmethod
    def create(cls, path, name=None):
        p = cls(path)
        p.path.mkdir(parents=True, exist_ok=True)
        if p.state_file.exists():
            p.load()
        else:
            p.state["created"] = datetime.datetime.now().isoformat(timespec="seconds")
            if name:
                p.state["name"] = name
        for d in (p.rootfs, p.isodir, p.output, p.cache, p.logs, p.bootdir):
            d.mkdir(exist_ok=True)
        p.save()
        return p

    @classmethod
    def open(cls, path):
        p = cls(path)
        if not p.state_file.is_file():
            raise FileNotFoundError("Not an Eduka-Customizer project: {}".format(p.path))
        p.load()
        for d in (p.output, p.cache, p.logs, p.bootdir):
            d.mkdir(exist_ok=True)
        return p

    def load(self):
        with open(self.state_file, encoding="utf-8") as fh:
            data = json.load(fh)
        merged = json.loads(json.dumps(DEFAULT_STATE))
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        self.state = merged

    def save(self):
        self.state["customizer_version"] = VERSION
        tmp = self.state_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.state_file)

    def lock(self):
        """Prevent two GUI/CLI instances from building the same project."""
        fh = open(self.path / ".lock", "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.close()
            raise ProjectLocked("Another Eduka-Customizer instance is using {}".format(self.path))
        fh.write(str(os.getpid()))
        fh.flush()
        self._lock_fh = fh

    def unlock(self):
        if self._lock_fh:
            fcntl.flock(self._lock_fh, fcntl.LOCK_UN)
            self._lock_fh.close()
            self._lock_fh = None

    # Helpers -----------------------------------------------------------
    @property
    def distro(self):
        return DistroInfo.from_dict(self.state.get("distro"))

    def has_rootfs(self):
        return all((self.rootfs / d).exists() for d in ("etc", "usr", "var"))

    def has_isotree(self):
        return (self.isodir / "live").is_dir()

    def record(self, action, detail=""):
        """Keep a short history; it doubles as a reproducible recipe log."""
        self.state.setdefault("history", []).append({
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "action": action, "detail": detail})
        self.state["history"] = self.state["history"][-500:]
        self.save()

    def mark_initramfs_dirty(self):
        self.state["initramfs_dirty"] = True
        self.save()
