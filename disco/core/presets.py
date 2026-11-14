"""Presets for automated builds (disco presets, disco build-all), saved under a name.

A preset holds the choices of a distribution (name, platform, Debian or Devuan
release, desktop, init system, installer, method) and its package lists. The
presets that come with D!sco are in /usr/share/disco/presets; your own are saved
in <projects folder>/presets. Both are plain JSON files: "disco presets export" writes
one, "disco presets apply NAME --file FILE" reads one.
"""

import json
import re
from pathlib import Path

from disco.core.config import data_file, settings
from disco.core.log import log

FIELDS = {
    "distro_name": "My Linux",
    "platform": "pc64",
    "family": "debian",          # debian | devuan
    "suite": "stable",           # oldstable | stable | testing | sid
    "variant": "important",      # mmdebstrap variant of the base
    "desktop": "xfce",           # an id from desktops.json, or "" for no desktop
    "dm": "",                    # display manager ("" = the desktop's own choice)
    "init": "systemd",           # systemd | sysvinit | openrc | runit
    "installer": "calamares",    # calamares | none | debs
    "method": "disco",           # disco (debootstrap/mmdebstrap -> chroot -> squashfs) | live-build
    "mirror": "",                # "" = the mirror on the Settings page
    "profile": "",               # a purpose from profiles.json (recommended apps)
}
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+,:()/!-]{0,79}$")


def builtin_dir():
    return Path(data_file("presets"))


def user_dir():
    return Path(settings().get("general", "projects_dir")) / "presets"


def file_name(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] + ".json"


def normalize(data):
    """A complete, checked preset."""
    if not isinstance(data, dict):
        raise ValueError("A preset is a JSON object")
    builder = dict(FIELDS)
    builder.update({k: v for k, v in (data.get("builder") or {}).items() if k in FIELDS})
    for key in FIELDS:
        if not isinstance(builder[key], str):
            raise ValueError("{} must be text".format(key))
    from disco.core import platforms
    platforms.get(builder["platform"])
    if builder["family"] not in ("debian", "devuan"):
        raise ValueError("family must be debian or devuan")
    if builder["suite"] not in ("oldstable", "stable", "testing", "sid"):
        raise ValueError("suite must be oldstable, stable, testing or sid")
    if builder["init"] not in ("systemd", "sysvinit", "openrc", "runit"):
        raise ValueError("init must be systemd, sysvinit, openrc or runit")
    if builder["family"] == "devuan" and builder["init"] == "systemd":
        builder["init"] = "sysvinit"
    if builder["installer"] not in ("calamares", "none", "debs"):
        raise ValueError("installer must be calamares, none or debs")
    if builder["method"] not in ("disco", "live-build"):
        raise ValueError("method must be disco or live-build")
    name = data.get("name") or builder["distro_name"]
    if not SAFE_NAME.match(name):
        raise ValueError("Preset names use letters, digits, spaces and . _ + - , : ( ) / ! (80 at most)")
    lists = data.get("lists") or {}
    if not isinstance(lists, dict):
        raise ValueError("lists must be an object")
    return {"name": name, "description": str(data.get("description", "")), "builder": builder, "lists": lists}


def available():
    """[(name, path, builtin)] of all presets, the ones of D!sco first."""
    out = []
    for folder, builtin in ((builtin_dir(), True), (user_dir(), False)):
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.json")):
            try:
                out.append((normalize(json.loads(p.read_text()))["name"], p, builtin))
            except (OSError, ValueError, KeyError) as e:
                log.warning("Preset %s skipped: %s", p, e)
    return out


def load(path):
    return normalize(json.loads(Path(path).read_text()))


def find(name):
    for n, p, _b in available():
        if n == name or p.stem == name:
            return load(p)
    raise KeyError("No preset called {}".format(name))


def from_project(project, name=None, description=""):
    from disco.core.pkglists import Lists
    builder = dict(FIELDS)
    builder.update({k: v for k, v in project.state.get("builder", {}).items() if k in FIELDS})
    lists = {}
    lst = Lists(project)
    for l in lst.all():
        lists[l.name] = {"title": l.title, "on": lst.is_on(l), "packages": l.packages(), "comment": l.comment()}
    return normalize({"name": name or builder["distro_name"], "description": description, "builder": builder,
                      "lists": lists})


def save(preset, path=None):
    """Save a preset among your own (or into *path*). Returns the file."""
    preset = normalize(preset)
    path = Path(path) if path else user_dir() / file_name(preset["name"])
    if not path or path.parent == builtin_dir():
        raise PermissionError("The presets of D!sco cannot be changed: save it under another name")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preset, indent=1, ensure_ascii=False) + "\n")
    return path


def delete(name):
    for n, p, builtin in available():
        if n == name:
            if builtin:
                raise PermissionError("{} comes with D!sco and cannot be deleted".format(name))
            p.unlink()
            return p
    raise KeyError("No preset called {}".format(name))


def apply(project, preset, lists=True):
    """Put a preset's choices (and package lists) into a project."""
    preset = normalize(preset)
    project.state.setdefault("builder", {}).update(preset["builder"])
    project.state["builder"]["preset"] = preset["name"]
    if preset["builder"]["distro_name"]:
        project.state["name"] = preset["builder"]["distro_name"]
    project.save()
    if lists:
        # The preset's own lists, completed with the standard lists of its platform.
        from disco.core import platforms
        from disco.core.pkglists import Lists
        b = preset["builder"]
        data = Lists.defaults(platforms.get(b["platform"]), b["profile"] or None, b["installer"])
        data.update(preset["lists"])
        Lists(project).load(data)
    project.record("preset", preset["name"])
