"""Fetch, build, install and pre-configure Eduka-Desktop.

Eduka-Desktop (https://github.com/hugomonizdorego/Eduka-Desktop) is kept
as a dpkg-deb tree (DEBIAN/ + usr/ + etc/).  A future debian/ source
layout is supported too and is built with dpkg-buildpackage.
"""

import ast
import json
import os
import re
import shutil
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.apt import Packages, parse_deb822
from eduka_customizer.core.config import settings
from eduka_customizer.core import fsutil
from eduka_customizer.core.log import log

COMMON_REL = "usr/lib/edukasaun-desktop/eduka_common.py"
SKEL_CONFIG = "etc/skel/.config/eduka-desktop"
SKIP_TOP = {".git", ".github", ".gitignore", "README.md", "README_0.9.10.txt", "LICENSE"}
REF_RE = re.compile(r"^[A-Za-z0-9._/+-]{1,200}$")

# Choices offered in the GUI for known keys.
CHOICES = {
    "position": ["Bottom", "Top"],
    "theme_style": ["Eduka-Default-Theme", "Liquid Glass"],
    "taskbar_style": ["Icon and Text", "Icon only", "Text only"],
    "layout": ["Grid", "List"],
    "mode": ["Eduka-Desktop"],
}


def read_control(path):
    stanzas = parse_deb822(Path(path).read_text(errors="replace"))
    return stanzas[0] if stanzas else {}


def parse_defaults(common_py):
    """Read DEFAULT_PANEL/MENU/DESKTOP and SETTINGS_REVISION without importing.

    eduka_common.py imports PyQt5 at module level, so it is parsed with ast
    instead of executed; names referencing simple constants are resolved.
    """
    tree = ast.parse(Path(common_py).read_text(errors="replace"))
    consts = {}
    result = {"SETTINGS_REVISION": "", "VERSION": "", "DEFAULT_PANEL": {},
              "DEFAULT_MENU": {}, "DEFAULT_DESKTOP": {}}

    def value(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name) and node.id in consts:
            return consts[node.id]
        raise ValueError

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant):
            consts[target.id] = node.value.value
        if target.id in result and isinstance(node.value, ast.Dict):
            d = {}
            for k, v in zip(node.value.keys, node.value.values):
                try:
                    d[value(k)] = value(v)
                except ValueError:
                    continue
            result[target.id] = d
    result["SETTINGS_REVISION"] = consts.get("SETTINGS_REVISION", "")
    result["VERSION"] = consts.get("VERSION", "")
    return result


def _is_script(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(2) == b"#!"
    except OSError:
        return False


class EdukaDesktop:
    def __init__(self, project):
        self.project = project
        self.src = project.cache / "eduka-desktop-src"
        self.build_dir = project.cache / "eduka-desktop-build"

    # Source ----------------------------------------------------------
    def fetch(self, repo=None, ref=None):
        cfg = settings()
        repo = repo or cfg.get("edukasaun", "eduka_desktop_repo")
        ref = ref if ref is not None else cfg.get("edukasaun", "eduka_desktop_ref")
        if ref and not REF_RE.match(ref):
            raise ValueError("Invalid git branch/tag: {}".format(ref))
        if os.path.isdir(repo):
            log.info("Using local Eduka-Desktop source %s", repo)
            if self.src.exists():
                shutil.rmtree(self.src)
            fsutil.copytree(repo, self.src, symlinks=True, ignore=shutil.ignore_patterns(".git"))
            return self.src
        runner.require("git")
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        if (self.src / ".git").is_dir():
            log.info("Updating Eduka-Desktop from %s", repo)
            runner.run(["git", "-C", self.src, "remote", "set-url", "origin", repo], env=env)
            runner.run(["git", "-C", self.src, "fetch", "--depth", "1", "origin", ref or "HEAD"], env=env)
            runner.run(["git", "-C", self.src, "reset", "--hard", "FETCH_HEAD"], env=env)
        else:
            if self.src.exists():
                shutil.rmtree(self.src)
            log.info("Cloning Eduka-Desktop from %s", repo)
            cmd = ["git", "clone", "--depth", "1"]
            if ref:
                cmd += ["--branch", ref]
            runner.run(cmd + [repo, self.src], env=env)
        rev = runner.output(["git", "-C", self.src, "rev-parse", "--short", "HEAD"], check=False)
        self.project.state.setdefault("eduka_desktop", {}).update({"repo": repo, "ref": ref, "commit": rev})
        self.project.save()
        return self.src

    def source_version(self):
        control = self.src / "DEBIAN/control"
        if control.is_file():
            return read_control(control).get("Version", "")
        changelog = self.src / "debian/changelog"
        if changelog.is_file():
            m = re.search(r"\(([^)]+)\)", changelog.read_text(errors="replace"))
            return m.group(1) if m else ""
        return ""

    # Build -----------------------------------------------------------
    def build(self):
        if (self.src / "DEBIAN/control").is_file():
            return self._build_tree()
        if (self.src / "debian/control").is_file():
            return self._build_source()
        raise RuntimeError("Eduka-Desktop source has neither DEBIAN/control nor debian/control")

    def _build_tree(self):
        runner.require("dpkg-deb")
        control = read_control(self.src / "DEBIAN/control")
        name = control.get("Package", "edukasaun-desktop-menu")
        version = control.get("Version", "0")
        stage = self.build_dir / "{}_{}".format(name, version)
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        stage.mkdir(parents=True)
        for item in self.src.iterdir():
            if item.name in SKIP_TOP or item.name.startswith(".") or item.name.startswith("README"):
                continue
            dest = stage / item.name
            if item.is_dir():
                fsutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest)
        self._fix_permissions(stage)
        size_kb = sum(f.stat().st_size for f in stage.rglob("*")
                      if f.is_file() and "DEBIAN" not in f.parts) // 1024
        ctrl = (stage / "DEBIAN/control").read_text()
        if re.search(r"(?m)^Installed-Size:", ctrl):
            ctrl = re.sub(r"(?m)^Installed-Size:.*$", "Installed-Size: {}".format(size_kb), ctrl)
        else:
            ctrl = ctrl.rstrip("\n") + "\nInstalled-Size: {}\n".format(size_kb)
        (stage / "DEBIAN/control").write_text(ctrl if ctrl.endswith("\n") else ctrl + "\n")
        deb = self.build_dir / "{}_{}_all.deb".format(name, version)
        log.info("Building %s", deb.name)
        runner.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", stage, deb])
        return deb

    def _fix_permissions(self, stage):
        for p in stage.rglob("*"):
            if p.is_symlink():
                continue
            rel = p.relative_to(stage)
            if p.is_dir():
                p.chmod(0o755)
            elif rel.parts[0] == "DEBIAN":
                p.chmod(0o755 if rel.name in ("preinst", "postinst", "prerm", "postrm", "config") else 0o644)
            elif (len(rel.parts) > 1 and rel.parts[-2] in ("bin", "sbin", "libexec")) or _is_script(p):
                p.chmod(0o755)
            else:
                p.chmod(0o644)

    def _build_source(self):
        runner.require("dpkg-buildpackage")
        log.info("Building Eduka-Desktop with dpkg-buildpackage")
        runner.run(["dpkg-buildpackage", "-us", "-uc", "-b"], cwd=self.src)
        debs = sorted(self.src.parent.glob("*.deb"), key=lambda p: p.stat().st_mtime)
        if not debs:
            raise RuntimeError("dpkg-buildpackage produced no .deb")
        self.build_dir.mkdir(parents=True, exist_ok=True)
        for d in debs:
            shutil.move(str(d), self.build_dir / d.name)
        return self.build_dir / debs[-1].name

    # Install ---------------------------------------------------------
    def install(self, deb):
        Packages(self.project).install_debs([deb])
        self.project.state.setdefault("eduka_desktop", {})["installed"] = Path(deb).name
        self.project.record("eduka-desktop-install", Path(deb).name)

    def fetch_build_install(self, repo=None, ref=None):
        self.fetch(repo, ref)
        deb = self.build()
        self.install(deb)
        return deb

    def installed_version(self):
        status = self.project.rootfs / "var/lib/dpkg/status"
        if not status.is_file():
            return ""
        for st in parse_deb822(status.read_text(errors="replace")):
            if st.get("Package") == "edukasaun-desktop-menu" and "installed" in st.get("Status", ""):
                return st.get("Version", "")
        return ""

    # Defaults (/etc/skel) ----------------------------------------------
    def schema(self):
        for base in (self.project.rootfs, self.src):
            common = Path(base) / COMMON_REL
            if common.is_file():
                return parse_defaults(common)
        return None

    def current_defaults(self):
        """Defaults merged with whatever is already stored in /etc/skel."""
        schema = self.schema() or {}
        result = {}
        for section, key in (("panel", "DEFAULT_PANEL"), ("menu", "DEFAULT_MENU"),
                             ("desktop", "DEFAULT_DESKTOP")):
            data = dict(schema.get(key, {}))
            p = self.project.rootfs / SKEL_CONFIG / section / "settings.json"
            try:
                data.update(json.loads(p.read_text()))
            except (OSError, ValueError):
                pass
            data.pop("_settings_revision", None)
            result[section] = data
        return result

    def write_defaults(self, panel=None, menu=None, desktop=None):
        """Store default settings for every new user (live user included)."""
        schema = self.schema() or {}
        revision = schema.get("SETTINGS_REVISION", "")
        current = self.current_defaults()
        for section, values in (("panel", panel), ("menu", menu), ("desktop", desktop)):
            if values is None:
                continue
            data = dict(current.get(section, {}))
            data.update(values)
            if revision and section in ("panel", "desktop"):
                # Without this marker Eduka-Desktop resets transparency on first start.
                data["_settings_revision"] = revision
            p = self.project.rootfs / SKEL_CONFIG / section / "settings.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n")
            log.info("Wrote default %s settings", section)
        self.project.record("eduka-desktop-defaults")
