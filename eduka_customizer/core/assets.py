"""Add look-and-feel files to the image: themes, icons, cursors, fonts,
wallpapers, Plymouth and SDDM themes.

Files, folders and archives (dropped on the window or chosen in a dialog)
are recognized by their content and copied to the place where Debian looks
for them. Wallpapers form a gallery from which one is the default.
"""

import re
import shutil
from pathlib import Path

from eduka_customizer.core import fsutil
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".svg")
FONT_SUFFIXES = (".ttf", ".otf", ".ttc")
SAFE_NAME = re.compile(r"[^A-Za-z0-9._+-]+")
KIND_LABEL = {"gtk-theme": "GTK theme", "icon-theme": "icon theme", "cursor-theme": "cursor theme",
              "font": "font", "wallpaper": "wallpaper", "plymouth": "Plymouth theme",
              "sddm-theme": "login screen theme (SDDM)", "deb": "package"}


def safe_name(name):
    name = SAFE_NAME.sub("-", name).strip("-.")
    return name or "item"


def classify_dir(d):
    """What a folder is, or None (then its sub-folders are looked at)."""
    index = d / "index.theme"
    if (d / "cursors").is_dir():
        return "cursor-theme"
    if index.is_file():
        text = index.read_text(errors="replace")
        if "[Icon Theme]" in text and "Directories" in text:
            return "icon-theme"
        if any((d / x).is_dir() for x in ("gtk-2.0", "gtk-3.0", "gtk-4.0", "xfwm4", "openbox-3", "cinnamon",
                                           "gnome-shell", "metacity-1", "marco")):
            return "gtk-theme"
    if any((d / x).is_dir() for x in ("gtk-3.0", "gtk-4.0")) and not index.exists():
        return "gtk-theme"
    if (d / "metadata.desktop").is_file() and any(d.glob("*.qml")):
        return "sddm-theme"
    if any(d.glob("*.plymouth")):
        return "plymouth"
    return None


class Assets:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.chroot = Chroot(project.rootfs)

    def os_id(self):
        return self.project.os_id()

    # Recognize -------------------------------------------------------------
    def scan(self, paths):
        """List (kind, name, source path) for everything found in *paths*."""
        found = []
        for p in paths:
            self._scan(Path(p), found, depth=0)
        return found

    def _scan(self, p, found, depth):
        if depth > 6 or p.is_symlink():
            return
        if p.is_dir():
            kind = classify_dir(p)
            if kind:
                found.append((kind, p.name, p))
                return
            for child in sorted(p.iterdir()):
                self._scan(child, found, depth + 1)
            return
        low = p.name.lower()
        if low.endswith(IMAGE_SUFFIXES):
            found.append(("wallpaper", p.name, p))
        elif low.endswith(FONT_SUFFIXES):
            found.append(("font", p.name, p))
        elif low.endswith(".deb"):
            found.append(("deb", p.name, p))
        elif low.endswith(".plymouth"):
            found.append(("plymouth", p.stem, p))

    # Install -----------------------------------------------------------------------
    def add(self, paths):
        """Install everything found in files, folders or archives; returns what was added."""
        tmp = self.project.cache / "assets-import"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        sources = []
        try:
            for i, p in enumerate(Path(x) for x in paths):
                if not p.exists():
                    raise FileNotFoundError(p)
                if p.is_file() and fsutil.is_archive(p):
                    sources.append(fsutil.extract_archive(p, tmp / "{}-{}".format(i, safe_name(p.name))))
                else:
                    sources.append(p)
            items = self.scan(sources)
            if not items:
                raise ValueError("Nothing usable found: expected themes, icons, cursors, fonts, wallpapers, "
                                 "Plymouth or SDDM themes, or their archives")
            added = []
            debs = [src for kind, _n, src in items if kind == "deb"]
            for kind, name, src in items:
                if kind == "deb":
                    continue
                added.append((kind, self._install(kind, name, src)))
            if debs:
                from eduka_customizer.core.apt import Packages
                Packages(self.project).install_debs(debs)
                added += [("deb", d.name) for d in debs]
            if any(k == "font" for k, _ in added) and (self.rootfs / "usr/bin/fc-cache").exists():
                with self.chroot:
                    self.chroot.run(["fc-cache", "-f"], check=False, quiet=True)
            for kind, name in added:
                log.info("Added %s: %s", KIND_LABEL.get(kind, kind), name)
            self.project.record("assets-add", ", ".join(n for _k, n in added))
            return added
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _install(self, kind, name, src):
        r = self.rootfs
        if kind == "plymouth":
            from eduka_customizer.core.plymouth import Plymouth
            return Plymouth(self.project).install(src)
        if kind == "wallpaper":
            return Wallpapers(self.project).add_file(src)
        if kind == "font":
            dest = r / "usr/share/fonts" / ("opentype" if src.suffix.lower() == ".otf" else "truetype") / \
                "eduka-custom" / safe_name(src.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            fsutil.copy_regular(src, dest)
            return dest.name
        target = {"gtk-theme": "usr/share/themes", "icon-theme": "usr/share/icons",
                  "cursor-theme": "usr/share/icons", "sddm-theme": "usr/share/sddm/themes"}[kind]
        dest = r / target / safe_name(name)
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        elif dest.exists() or dest.is_symlink():
            dest.unlink()
        fsutil.copytree(src, dest, symlinks=True)
        if kind == "icon-theme" and (r / "usr/bin/gtk-update-icon-cache").exists():
            with self.chroot:
                self.chroot.run(["gtk-update-icon-cache", "-f", "-q", "/" + str(dest.relative_to(r))],
                                check=False, quiet=True)
        return dest.name


class Wallpapers:
    """A folder of wallpapers in the image; one of them is the default."""

    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs

    @property
    def folder(self):
        return self.rootfs / "usr/share/backgrounds" / safe_name(self.project.os_id())

    def list(self):
        if not self.folder.is_dir():
            return []
        return sorted(p for p in self.folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)

    def default(self):
        name = self.project.state.get("wallpapers", {}).get("default", "")
        return name if name and (self.folder / name).exists() else ""

    def add_file(self, src):
        src = Path(src)
        if src.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError("Not a picture: {}".format(src.name))
        self.folder.mkdir(parents=True, exist_ok=True)
        stem, suffix = safe_name(src.stem), src.suffix.lower()
        dest = self.folder / (stem + suffix)
        n = 2
        while dest.exists():
            dest = self.folder / "{}-{}{}".format(stem, n, suffix)
            n += 1
        fsutil.copy_regular(src, dest)
        self._register()
        if not self.default():
            self.set_default(dest.name)
        return dest.name

    def add(self, paths):
        added = []
        for p in paths:
            p = Path(p)
            files = sorted(f for f in p.rglob("*") if f.is_file()) if p.is_dir() else [p]
            added += [self.add_file(f) for f in files if f.suffix.lower() in IMAGE_SUFFIXES]
        return added

    def remove(self, name):
        p = self.folder / Path(name).name
        if not p.is_file():
            raise FileNotFoundError(name)
        was_default = self.project.state.get("wallpapers", {}).get("default") == p.name
        p.unlink()
        if was_default:
            self.project.state.setdefault("wallpapers", {})["default"] = ""
            rest = self.list()
            if rest:
                self.set_default(rest[0].name)
        self._register()
        self.project.save()

    def set_default(self, name):
        from eduka_customizer.core.branding import Branding
        p = self.folder / Path(name).name
        if not p.is_file():
            raise FileNotFoundError(name)
        Branding(self.project).set_wallpaper(p)
        self.project.state.setdefault("wallpapers", {})["default"] = p.name
        self.project.save()

    def _register(self):
        """Offer all pictures in the wallpaper choosers of GNOME, Cinnamon and MATE."""
        items = "".join(
            "  <wallpaper deleted=\"false\">\n    <name>{name}</name>\n    <filename>/{path}</filename>\n"
            "    <options>zoom</options>\n  </wallpaper>\n".format(
                name=p.stem.replace("&", "and").replace("<", "").replace(">", ""),
                path=p.relative_to(self.rootfs)) for p in self.list())
        xml = ("<?xml version=\"1.0\"?>\n<!DOCTYPE wallpapers SYSTEM \"gnome-wp-list.dtd\">\n"
               "<wallpapers>\n{}</wallpapers>\n".format(items))
        name = self.folder.name + ".xml"
        for d in ("gnome-background-properties", "cinnamon-background-properties", "mate-background-properties"):
            target = self.rootfs / "usr/share" / d / name
            if items:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(xml)
            elif target.exists():
                target.unlink()
