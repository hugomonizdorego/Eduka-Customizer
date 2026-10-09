"""What the extracted ISO says about itself: its identity (os-release, host
name, volume label, live user) and its artwork (logo, wallpaper, login and
GRUB backgrounds, installer colors). The Identity and Branding pages start
from these values, so you change what the ISO already is."""

import os
import re
import shutil
from pathlib import Path

from eduka_customizer.core import yamlconf

COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def os_release(rootfs):
    for rel in ("etc/os-release", "usr/lib/os-release"):
        p = Path(rootfs, rel)
        if p.is_symlink():
            target = os.readlink(p)
            p = Path(rootfs, target.lstrip("/")) if target.startswith("/") else p.parent / target
        if p.is_file():
            out = {}
            for line in p.read_text(errors="replace").splitlines():
                m = re.match(r'^([A-Z_]+)=(.*)$', line.strip())
                if m:
                    out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
            return out
    return {}


def _inside(rootfs, path):
    """Resolve *path* (absolute inside the image, links followed) to a file of the image."""
    rootfs = Path(rootfs)
    p = rootfs / str(path).lstrip("/")
    for _ in range(10):
        if not p.is_symlink():
            break
        target = os.readlink(p)
        p = rootfs / target.lstrip("/") if target.startswith("/") else p.parent / target
    return p if p.is_file() else None


def identity(project):
    """{name, id, version, codename, home_url, support_url, bug_url, hostname, volume_label, live_user}."""
    r = project.rootfs
    rel = os_release(r)
    out = {
        "name": rel.get("NAME", ""),
        "id": rel.get("ID", ""),
        "version": rel.get("VERSION_ID", "") or re.sub(r"\s*\(.*\)", "", rel.get("VERSION", "")),
        "codename": rel.get("DISTRO_CODENAME", "") or rel.get("VERSION_CODENAME", ""),
        "home_url": rel.get("HOME_URL", ""),
        "support_url": rel.get("SUPPORT_URL", ""),
        "bug_url": rel.get("BUG_REPORT_URL", ""),
        "pretty_name": rel.get("PRETTY_NAME", ""),
    }
    host = Path(r, "etc/hostname")
    out["hostname"] = host.read_text(errors="replace").strip().split("\n")[0] if host.is_file() else ""
    if out["hostname"] in ("localhost", "") and out["id"]:
        out["hostname"] = out["id"]
    out["volume_label"] = (project.state.get("source", {}) or {}).get("volume_id", "") or ""
    user = ""
    for conf in sorted(Path(r, "etc/live/config.conf.d").glob("*.conf")) + [Path(r, "etc/live/config.conf")]:
        if conf.is_file():
            m = re.search(r'(?m)^\s*LIVE_USERNAME="?([a-z_][a-z0-9_-]*)"?', conf.read_text(errors="replace"))
            if m:
                user = m.group(1)
    out["live_user"] = user
    return out


def artwork(project):
    """Image files of the ISO: {logo, wallpaper, login_background, grub_background, accent, dark}."""
    r = project.rootfs
    rel = os_release(r)
    os_id = rel.get("ID", "debian")
    found = {}
    logos = ["usr/share/pixmaps/{}-logo.png".format(os_id), "usr/share/pixmaps/{}-logo.svg".format(os_id),
             "usr/share/icons/hicolor/256x256/apps/{}-logo.png".format(os_id),
             "usr/share/icons/hicolor/scalable/apps/{}-logo.svg".format(os_id),
             "usr/share/icons/desktop-base/256x256/emblems/emblem-{}.png".format(os_id),
             "usr/share/icons/hicolor/256x256/apps/distributor-logo.png",
             "usr/share/pixmaps/debian-logo.png", "usr/share/icons/desktop-base/256x256/emblems/emblem-debian.png"]
    cal = _calamares_branding(r)
    if cal.get("productLogo"):
        logos.insert(0, cal["productLogo"])
    for cand in logos:
        p = _inside(r, cand)
        if p:
            found["logo"] = p
            break
    for key, cands in (("wallpaper", ["usr/share/images/desktop-base/default",
                                      "usr/share/images/desktop-base/desktop-background",
                                      "usr/share/desktop-base/active-theme/wallpaper/contents/images/1920x1080.svg",
                                      "usr/share/backgrounds/default.png", "usr/share/backgrounds/default.jpg"]),
                       ("login_background", ["usr/share/images/desktop-base/login-background.svg",
                                             "usr/share/desktop-base/active-theme/login/background.svg"]),
                       ("grub_background", ["usr/share/images/desktop-base/desktop-grub.png",
                                            "usr/share/desktop-base/active-theme/grub/grub-4x3.png"])):
        for cand in cands:
            p = _inside(r, cand)
            if p:
                found[key] = p
                break
    style = {k[0].lower() + k[1:]: v for k, v in (cal.get("style") or {}).items()}
    out = {k: str(v) for k, v in found.items()}
    if COLOR.match(str(style.get("sidebarTextHighlight", ""))):
        out["accent"] = style["sidebarTextHighlight"]
    if COLOR.match(str(style.get("sidebarBackground", ""))):
        out["dark"] = style["sidebarBackground"]
    return out


def _calamares_branding(rootfs):
    settings = Path(rootfs, "etc/calamares/settings.conf")
    if not settings.is_file():
        return {}
    name = str(yamlconf.load(settings.read_text(errors="replace")).get("branding") or "debian")
    d = Path(rootfs, "etc/calamares/branding", name)
    desc = d / "branding.desc"
    if not desc.is_file():
        return {}
    data = yamlconf.load(desc.read_text(errors="replace"))
    out = {"style": data.get("style") or {}}
    logo = (data.get("images") or {}).get("productLogo")
    if logo:
        out["productLogo"] = str(logo) if str(logo).startswith("/") else "/" + str(
            (d / str(logo)).relative_to(rootfs))
    return out


def copy_artwork(project, art=None):
    """Copy the ISO's artwork into the project (PROJECT/from-iso/), so later changes to the
    image never change the originals. Returns {key: copied path}."""
    art = art if art is not None else artwork(project)
    dest = Path(project.path, "from-iso")
    dest.mkdir(parents=True, exist_ok=True)
    out = {}
    for key in ("logo", "wallpaper", "login_background", "grub_background"):
        src = art.get(key)
        if src and Path(src).is_file():
            target = dest / (key + Path(src).suffix.lower())
            shutil.copy2(src, target)
            out[key] = str(target)
    for key in ("accent", "dark"):
        if art.get(key):
            out[key] = art[key]
    return out
