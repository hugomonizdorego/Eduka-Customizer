"""Easy branding: choose a picture, tick "Set as default", press Apply (Wallpaper & Logo page).

  wallpaper  the desktop picture of every user (Xfce, GNOME, KDE, Cinnamon, MATE, LXQt...)
  logo       the system logo: menu icon, os-release LOGO, login screen, installer, boot splash
  login      the background of the login screen
  boot       the background of the boot menus: the ISO (GRUB and ISOLINUX) and installed GRUB
  user       the picture of new users (/etc/skel/.face)

Every picture is kept in <project>/branding/pictures, a folder of yours. Without
"Set as default" the picture is only added to the system (the wallpaper gallery,
/usr/share/pixmaps/<id>/) so users can pick it themselves.
"""

import shutil
from pathlib import Path

from disco.core.log import log

KINDS = [
    ("wallpaper", "Desktop wallpaper", "Set as the default wallpaper",
     "The picture on the desktop of every user (Xfce, GNOME, KDE Plasma, Cinnamon, MATE, LXQt, Eduka-Desktop)."),
    ("logo", "Logo", "Use as the logo everywhere",
     "Menu and system icon, os-release LOGO, login screen, installer and the boot splash."),
    ("login", "Login screen", "Set as the login screen background",
     "The background of LightDM, SDDM or GDM."),
    ("boot", "Boot menu", "Set as the boot menu background",
     "The menu of the ISO (GRUB and ISOLINUX) and GRUB of computers installed from it."),
    ("user", "Picture of new users", "Set as the picture of new users",
     "The picture every new user starts with (/etc/skel/.face)."),
]
PICTURES = ("*.png", "*.jpg", "*.jpeg", "*.svg", "*.webp")
EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".webp")


def folder(project):
    d = Path(project.path) / "branding" / "pictures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stored(project, kind):
    """The picture chosen for *kind* (in the project's pictures folder), or None."""
    entry = (project.state.get("quickbrand") or {}).get(kind) or {}
    p = Path(entry.get("file", "")) if entry.get("file") else None
    return p if p and p.is_file() else None


def is_default(project, kind):
    return bool(((project.state.get("quickbrand") or {}).get(kind) or {}).get("default", True))


def store(project, kind, image, default=True):
    """Keep a copy of *image* in the project (the original may be on a USB stick)."""
    if kind not in {k for k, *_ in KINDS}:
        raise ValueError("Unknown picture: {}".format(kind))
    image = Path(image)
    if image.suffix.lower() not in EXTENSIONS or not image.is_file():
        raise ValueError("Choose a PNG, JPEG, SVG or WebP picture")
    dest = folder(project) / (kind + image.suffix.lower())
    for old in folder(project).glob(kind + ".*"):
        if old != dest:
            old.unlink()
    if image.resolve() != dest.resolve():
        shutil.copy2(image, dest)
    from disco.core import permissions
    permissions.give_to_user(dest)
    project.state.setdefault("quickbrand", {})[kind] = {"file": str(dest), "default": bool(default)}
    project.save()
    return dest


def apply(project, kind):
    """Put the stored picture into the system: as the default, or only into the system's pictures."""
    image = stored(project, kind)
    if image is None:
        raise ValueError("Choose a picture first")
    from disco.core.branding import Branding
    br = Branding(project)
    if not is_default(project, kind):
        return _add_only(project, kind, image)
    if kind == "wallpaper":
        br.set_wallpaper(image)
    elif kind == "logo":
        apply_logo(project, image)
    elif kind == "login":
        br.set_login_screen(background=image)
    elif kind == "boot":
        _boot_background(project, image)
    elif kind == "user":
        from disco.core import sysfiles
        sysfiles.set_face(project, image)
    project.record("easy-branding", kind)
    log.info("%s: %s applied", dict((k, t) for k, t, *_ in KINDS)[kind], image.name)


def _add_only(project, kind, image):
    if kind == "wallpaper":
        d = Path(project.rootfs) / "usr/share/backgrounds" / project.os_id()
    else:
        d = Path(project.rootfs) / "usr/share/pixmaps" / project.os_id()
    d.mkdir(parents=True, exist_ok=True)
    target = d / "{}{}".format(kind if kind != "wallpaper" else image.stem + "-" + kind, image.suffix.lower())
    shutil.copy2(image, target)
    target.chmod(0o644)
    log.info("%s added to %s (not the default)", image.name, "/" + str(target.relative_to(project.rootfs)))
    return target


def apply_logo(project, image):
    """The logo everywhere: icons, os-release LOGO, login screen, installer and boot splash."""
    from disco.core import imaging
    from disco.core.branding import Branding
    r = Path(project.rootfs)
    os_id = project.os_id()
    icons = r / "usr/share/icons/hicolor"
    for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        for name in (os_id + "-logo", "distributor-logo-" + os_id):
            imaging.write_png(image, icons / "{0}x{0}/apps/{1}.png".format(size, name), (size, size), fit="contain")
    if str(image).lower().endswith(".svg"):
        dest = icons / "scalable/apps" / (os_id + "-logo.svg")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, dest)
    imaging.write_png(image, r / "usr/share/pixmaps" / (os_id + "-logo.png"), (256, 256), fit="contain")
    # os-release names the icon (LOGO=<id>-logo)
    from disco.core import sysfiles
    from disco.core.distro import format_os_release, parse_os_release
    text = sysfiles.read(project, "etc/os-release")
    if text:
        data = parse_os_release(text)
        data["LOGO"] = os_id + "-logo"
        sysfiles.write(project, "etc/os-release", format_os_release(data))
    br = Branding(project)
    try:
        br.set_login_screen(greeter_logo=image)
    except (OSError, ValueError) as e:
        log.warning("Login screen logo not set: %s", e)
    from disco.core.calamares import Calamares
    cal = Calamares(project)
    if cal.installed():
        try:
            cal.set_branding(images={"productLogo": str(image), "productIcon": str(image)})
        except (OSError, ValueError, FileNotFoundError) as e:
            log.warning("Installer logo not set: %s", e)
    # A boot splash made from the logo (only when no other theme was chosen)
    current = br.plymouth_current()
    if current in ("", "spinner", "bgrt", "text", "details", "tribar", "emerald", "homeworld", "lines",
                   "moonlight", "softwaves", "ceratopsian", os_id):
        try:
            name = br.generate_plymouth(os_id, image, background="#1a237e", spinner_color="#ffd54f")
            br.set_plymouth(name)
        except Exception as e:  # the logo is set even without a splash
            log.warning("Boot splash not made from the logo: %s", e)
    project.state.setdefault("identity", {})["logo"] = os_id + "-logo"
    project.save()


def _boot_background(project, image):
    """The ISO's boot menus (kept for every build) and GRUB of installed computers."""
    project.state.setdefault("boot", {})["splash"] = str(image)
    project.save()
    isodir = Path(project.isodir)
    if (isodir / "boot/grub").is_dir() or (isodir / "isolinux").is_dir():
        from disco.core import bootloader
        bootloader.set_splash(isodir, image)
    from disco.core import sysfiles
    sysfiles.set_grub_background(project, image)
