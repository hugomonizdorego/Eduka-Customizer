"""Third-party GRUB themes (theme.txt with its pictures and fonts).

A theme is checked before it is used and refused when GRUB could not show it:
no theme.txt, pictures GRUB cannot read (only PNG, JPEG and TGA), files the
theme refers to that are missing, fonts that are not .pf2, or a size that does
not belong on a boot medium. Accepted themes are copied to the ISO
(/boot/grub/themes/<name>) and, if wanted, to the installed system.
"""

import re
import shutil
import tarfile
import zipfile
from pathlib import Path

from eduka_customizer.core import fsutil
from eduka_customizer.core.log import log

IMAGE_OK = {".png", ".jpg", ".jpeg", ".tga"}
IMAGE_ANY = IMAGE_OK | {".svg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".xcf", ".psd"}
MAX_SIZE = 25 * 1024 * 1024
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,60}$")
BEGIN, END = "# eduka-grub-theme-begin", "# eduka-grub-theme-end"
GRUB_D = "etc/default/grub.d/96-eduka-grub-theme.cfg"


class ThemeRejected(ValueError):
    """The theme cannot be shown by GRUB; the message says why."""


def unpack(source, work):
    """Copy or extract *source* (folder, .zip, .tar.*) into *work*; return the folder with theme.txt."""
    source, work = Path(source), Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    if source.is_dir():
        fsutil.copytree(source, work / source.name, symlinks=False)
    elif zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as zf:
            for n in zf.namelist():
                if n.startswith("/") or ".." in Path(n).parts:
                    raise ThemeRejected("Unsafe path in the archive: {}".format(n))
            zf.extractall(work)
    elif tarfile.is_tarfile(source):
        with tarfile.open(source) as tf:
            for m in tf.getmembers():
                if m.name.startswith("/") or ".." in Path(m.name).parts or m.isdev() or m.issym() or m.islnk():
                    raise ThemeRejected("Unsafe entry in the archive: {}".format(m.name))
            try:
                tf.extractall(work, filter="data")
            except TypeError:
                tf.extractall(work)
    else:
        raise ThemeRejected("{} is not a folder, .zip or .tar archive".format(source.name))
    found = sorted(work.rglob("theme.txt"), key=lambda p: len(p.parts))
    if not found:
        raise ThemeRejected("No theme.txt: this is not a GRUB theme")
    return found[0].parent


def _image_size(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(32)
        if head.startswith(b"\x89PNG"):
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    except OSError:
        pass
    return None


def check(theme_dir):
    """(problems, warnings, info) for a theme folder. problems mean: refuse the theme."""
    d = Path(theme_dir)
    problems, warnings = [], []
    txt = d / "theme.txt"
    try:
        text = txt.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ["theme.txt cannot be read as text"], [], {}
    files = [p for p in d.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    if size > MAX_SIZE:
        problems.append("The theme is {:.0f} MiB; a boot theme must stay below {} MiB".format(
            size / 1024 ** 2, MAX_SIZE // 1024 ** 2))
    # Pictures named in theme.txt (desktop-image, *_pixmap_style patterns, scrollbar, icons ...)
    refs = re.findall(r'(?m)(?:desktop-image|scrollbar_frame|scrollbar_thumb|[a-z_]*pixmap_style|file)\s*[:=]\s*"([^"]+)"',
                      text)
    for ref in refs:
        if Path(ref).is_absolute() or ".." in Path(ref).parts:
            problems.append("theme.txt refers to a file outside the theme: {}".format(ref))
            continue
        ext = Path(ref.replace("*", "x")).suffix.lower()
        if ext and ext in IMAGE_ANY and ext not in IMAGE_OK:
            problems.append("{}: GRUB can only show PNG, JPEG and TGA pictures".format(ref))
            continue
        if "*" in ref:
            if not list(d.glob(ref)):
                problems.append("No picture matches {} (named in theme.txt)".format(ref))
        elif not (d / ref).exists():
            problems.append("{} is named in theme.txt but missing".format(ref))
    bad_images = sorted({p.suffix.lower() for p in files if p.suffix.lower() in IMAGE_ANY - IMAGE_OK})
    if bad_images and not problems:
        warnings.append("Pictures GRUB cannot read are ignored: {}".format(", ".join(bad_images)))
    fonts = sorted(p for p in files if p.suffix.lower() == ".pf2")
    other_fonts = [p.name for p in files if p.suffix.lower() in (".ttf", ".otf")]
    named = set(re.findall(r'(?m)(?:font|item_font|title-font|message-font|terminal-font)\s*[:=]\s*"([^"]+)"', text))
    if named and not fonts:
        if other_fonts:
            problems.append("The theme has TTF/OTF fonts ({}); GRUB needs .pf2 fonts (convert them with "
                            "grub-mkfont)".format(", ".join(other_fonts[:3])))
        elif not all(n.lower().startswith("unifont") for n in named):
            warnings.append("Fonts {} are not in the theme: GRUB falls back to its own font".format(
                ", ".join(sorted(named))))
    bg = re.search(r'(?m)desktop-image\s*:\s*"([^"]+)"', text)
    info = {"name": d.name, "size": size, "fonts": [p.name for p in fonts], "files": len(files)}
    if bg and (d / bg.group(1)).exists():
        dims = _image_size(d / bg.group(1))
        if dims:
            info["background"] = "{}×{}".format(*dims)
            if dims[0] < 640 or dims[1] < 480:
                warnings.append("The background is only {}×{}".format(*dims))
    if "+ boot_menu" not in text and "+boot_menu" not in text.replace(" ", ""):
        warnings.append("theme.txt has no boot_menu: GRUB will draw the menu its own way")
    return problems, warnings, info


def theme_block(name, fonts):
    lines = [BEGIN, "insmod gfxterm", "insmod png", "insmod jpeg", "insmod tga"]
    lines += ["loadfont /boot/grub/themes/{}/{}".format(name, f) for f in fonts]
    lines += ["set gfxmode=auto", "terminal_output gfxterm",
              "set theme=/boot/grub/themes/{}/theme.txt".format(name), "export theme", END]
    return "\n".join(lines) + "\n"


def _strip(text):
    return re.sub(r"(?s)\n?{}.*?{}\n?".format(re.escape(BEGIN), re.escape(END)), "\n", text).rstrip("\n") + "\n"


def iso_grub_cfgs(isodir):
    return [p for p in (Path(isodir, "boot/grub/grub.cfg"),) if p.exists()]


class GrubThemes:
    def __init__(self, project):
        self.project = project
        self.isodir = Path(project.isodir)
        self.rootfs = Path(project.rootfs)

    def installed(self):
        d = self.isodir / "boot/grub/themes"
        return sorted(p.name for p in d.iterdir() if (p / "theme.txt").exists()) if d.is_dir() else []

    def current(self):
        return self.project.state.get("boot", {}).get("grub_theme", "")

    def add(self, source, installed_system=False):
        """Check and add a theme; raises ThemeRejected with every reason when GRUB could not use it."""
        work = Path(self.project.cache) / "grub-theme"
        try:
            d = unpack(source, work)
            problems, warnings, info = check(d)
            if problems:
                raise ThemeRejected("This GRUB theme is not compatible:\n• " + "\n• ".join(problems))
            name = re.sub(r"[^A-Za-z0-9._+-]", "-", d.name if d != work else Path(source).stem)[:60] or "theme"
            if not SAFE.match(name):
                name = "theme"
            dest = self.isodir / "boot/grub/themes" / name
            if dest.exists():
                shutil.rmtree(dest)
            fsutil.copytree(d, dest, symlinks=False)
            if installed_system:
                inst = self.rootfs / "boot/grub/themes" / name
                if inst.exists():
                    shutil.rmtree(inst)
                fsutil.copytree(d, inst, symlinks=False)
            info["name"] = name
            log.info("GRUB theme %s added (%d files)", name, info["files"])
            return name, warnings, info
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def use(self, name, installed_system=False):
        """Show *name* in the ISO's GRUB menu (and in the installed system's)."""
        d = self.isodir / "boot/grub/themes" / name
        if not SAFE.match(name) or not (d / "theme.txt").exists():
            raise FileNotFoundError("No GRUB theme called {} in the ISO".format(name))
        fonts = sorted(p.name for p in d.glob("*.pf2"))
        for cfg in iso_grub_cfgs(self.isodir):
            cfg.write_text(_strip(cfg.read_text(errors="replace")) + theme_block(name, fonts))
        drop = self.rootfs / GRUB_D
        if installed_system:
            inst = self.rootfs / "boot/grub/themes" / name
            if not inst.exists():
                fsutil.copytree(d, inst, symlinks=False)
            drop.parent.mkdir(parents=True, exist_ok=True)
            drop.write_text('# GRUB theme chosen in DistroForge\nGRUB_THEME="/boot/grub/themes/{}/theme.txt"\n'
                            'GRUB_GFXMODE=auto\n'.format(name))
        elif drop.exists():
            drop.unlink()
        self.project.state.setdefault("boot", {}).update({"grub_theme": name,
                                                          "grub_theme_installed": bool(installed_system)})
        self.project.save()
        self.project.record("grub-theme", name)

    def reapply(self):
        """After the boot menu is regenerated by a build."""
        name = self.current()
        if name and (self.isodir / "boot/grub/themes" / name / "theme.txt").exists():
            self.use(name, self.project.state.get("boot", {}).get("grub_theme_installed", False))

    def remove(self):
        for cfg in iso_grub_cfgs(self.isodir):
            cfg.write_text(_strip(cfg.read_text(errors="replace")))
        drop = self.rootfs / GRUB_D
        if drop.exists():
            drop.unlink()
        self.project.state.setdefault("boot", {}).pop("grub_theme", None)
        self.project.save()
