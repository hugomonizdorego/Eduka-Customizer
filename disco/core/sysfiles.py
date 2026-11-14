"""The files that tell who the system is, edited directly (System files page).

  /etc/os-release (-> /usr/lib/os-release)   NAME, VERSION, ID, PRETTY_NAME, HOME_URL, LOGO...
  /etc/lsb-release                            DISTRIB_ID, DISTRIB_RELEASE, DISTRIB_DESCRIPTION
  /etc/issue, /etc/issue.net                  the text before the login prompt ("Welcome to ...")
  /etc/hostname, /etc/hosts                   the computer name (127.0.1.1)
  /etc/motd                                   the message after logging in on a console or over SSH

Every file gets a template made from the Identity page; you change it as you like.
Also here: the user skeleton (/etc/skel: the picture of new users, settings folders
copied from this computer) and the GRUB background of installed systems.
"""

import re
import shutil
from pathlib import Path

from disco.core.distro import format_lsb_release, format_os_release, parse_os_release, resolve_in_root
from disco.core.log import log

FILES = [
    ("etc/os-release", "os-release", "Name, version and ID of the system, read by every program that shows "
                                     "which system it runs on (the real file is /usr/lib/os-release)."),
    ("etc/lsb-release", "lsb-release", "The older form of the same information (DISTRIB_ID...)."),
    ("etc/issue", "issue", "Shown before the login prompt of text consoles. \\n is the host name, \\l the console."),
    ("etc/issue.net", "issue.net", "Shown before remote (telnet) logins."),
    ("etc/hostname", "hostname", "The name of the computer."),
    ("etc/hosts", "hosts", "Names of this computer for the network; 127.0.1.1 is the computer's own name."),
    ("etc/motd", "motd", "Message of the day, shown after logging in on a console or over SSH."),
]
KNOWN = {rel for rel, _t, _d in FILES}
GRUB_DROPIN = "etc/default/grub.d/90-disco-background.cfg"
SKEL_FACE = "etc/skel/.face"


def _real(project, rel):
    """The file inside the image (links followed inside it), never outside the image."""
    rootfs = Path(project.rootfs)
    path = resolve_in_root(rootfs, rel)
    if path is None:
        raise ValueError("{} cannot be resolved inside the image".format(rel))
    real = path.resolve() if path.exists() else path.parent.resolve() / path.name
    root = rootfs.resolve()
    if real != root and root not in real.parents:
        raise ValueError("{} leads outside the image".format(rel))
    return path


def read(project, rel):
    if rel not in KNOWN:
        raise ValueError("Not a system file of this page: {}".format(rel))
    p = _real(project, rel)
    return p.read_text(errors="replace") if p.is_file() else ""


def write(project, rel, text):
    """Write a system file of the image (as root, mode 644)."""
    if rel not in KNOWN:
        raise ValueError("Not a system file of this page: {}".format(rel))
    check(rel, text)
    p = _real(project, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if text.endswith("\n") else text + "\n")
    p.chmod(0o644)
    if rel == "etc/hostname":
        name = text.strip()
        hosts = _real(project, "etc/hosts")
        old = hosts.read_text(errors="replace") if hosts.exists() else "127.0.0.1\tlocalhost\n"
        if re.search(r"(?m)^127\.0\.1\.1\s", old):
            new = re.sub(r"(?m)^127\.0\.1\.1\s.*$", "127.0.1.1\t" + name, old)
        else:
            new = old.rstrip("\n") + "\n127.0.1.1\t{}\n".format(name)
        hosts.write_text(new)
        project.state.setdefault("identity", {})["hostname"] = name
        project.save()
    project.record("system-file", "/" + rel)
    log.info("Wrote /%s", rel)


def check(rel, text):
    """ValueError for text the system would not understand."""
    if rel == "etc/hostname":
        name = text.strip()
        if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", name):
            raise ValueError("Host names use lower-case letters, digits and '-' (for example mylinux)")
    if rel in ("etc/os-release", "etc/lsb-release"):
        for n, line in enumerate(text.splitlines(), 1):
            if line.strip() and not line.lstrip().startswith("#") and not re.match(r"^[A-Z0-9_]+=", line):
                raise ValueError("Line {} of {} is not KEY=value: {}".format(n, rel, line[:60]))
        if rel == "etc/os-release":
            data = parse_os_release(text)
            for key in ("NAME", "ID"):
                if not data.get(key):
                    raise ValueError("os-release needs {}".format(key))
            if not re.match(r"^[a-z0-9._-]+$", data["ID"]):
                raise ValueError("ID uses lower-case letters, digits and . _ - only")


def template(project, rel):
    """A new text for *rel* made from the Identity page."""
    ident = project.state.get("identity") or {}
    name = ident.get("name") or project.display_name()
    os_id = ident.get("id") or project.os_id()
    version = ident.get("version") or ""
    codename = ident.get("codename") or ""
    pretty = "{} {}{}".format(name, version, " ({})".format(codename) if codename else "").strip()
    host = ident.get("hostname") or os_id
    info = project.distro
    if rel == "etc/os-release":
        logo = os_id + "-logo"
        data = {"PRETTY_NAME": pretty, "NAME": name, "VERSION_ID": version,
                "VERSION": "{}{}".format(version, " ({})".format(codename) if codename else ""),
                "VERSION_CODENAME": info.debian_codename or "", "ID": os_id, "ID_LIKE": "debian",
                "HOME_URL": ident.get("home_url", ""), "SUPPORT_URL": ident.get("support_url", ""),
                "BUG_REPORT_URL": ident.get("bug_url", ""), "LOGO": logo}
        return format_os_release({k: v for k, v in data.items() if v})
    if rel == "etc/lsb-release":
        return format_lsb_release(name, version, info.debian_codename or "", pretty)
    if rel == "etc/issue":
        return "Welcome to {} - \\n \\l\n\n".format(pretty)
    if rel == "etc/issue.net":
        return "Welcome to {}\n".format(pretty)
    if rel == "etc/hostname":
        return host + "\n"
    if rel == "etc/hosts":
        return ("127.0.0.1\tlocalhost\n127.0.1.1\t{}\n\n# The following lines are desirable for IPv6 capable hosts\n"
                "::1     localhost ip6-localhost ip6-loopback\nff02::1 ip6-allnodes\nff02::2 ip6-allrouters\n"
                .format(host))
    if rel == "etc/motd":
        url = ident.get("home_url") or ""
        return ("\nWelcome to {}!\n{}\nThe programs included with this system are free software; the exact\n"
                "distribution terms for each program are described in the files in /usr/share/doc/*/copyright.\n"
                .format(pretty, "Website: {}\n".format(url) if url else ""))
    raise ValueError("No template for {}".format(rel))


# The user skeleton -------------------------------------------------------------------------------------
def set_face(project, image):
    """The picture of every new user (/etc/skel/.face), also the login screen's default user picture."""
    from disco.core import imaging
    target = Path(project.rootfs) / SKEL_FACE
    imaging.write_png(image, target, (256, 256), fit="cover")
    target.chmod(0o644)
    shared = Path(project.rootfs) / "usr/share/pixmaps/{}-user.png".format(project.os_id())
    shared.parent.mkdir(parents=True, exist_ok=True)   # minimal systems have no pixmaps folder
    shutil.copy2(target, shared)
    from disco.core.branding import _ini_set
    if (Path(project.rootfs) / "usr/sbin/lightdm-gtk-greeter").exists():
        _ini_set(Path(project.rootfs) / "etc/lightdm/lightdm-gtk-greeter.conf.d/60-disco-face.conf", "greeter",
                 {"default-user-image": "/" + str(shared.relative_to(project.rootfs))})
    project.record("skel-face", Path(image).name)
    return target


# What a settings folder of this computer must not take into the home of every new user: passwords,
# cookies, keys, tokens, histories, caches and open sessions. Names are compared without case.
PRIVATE = (
    "*cache*", "*.lock", "lock", "lockfile", "singleton*", "*.socket", "*.pid", "*.log", "*history*",
    "*keyring*", "*.kdbx", "*.keystore", "*token*", "*secret*", "*password*", "*credential*", "*.pem", "*.key",
    "*.p12", "*.pfx", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*", "private-keys-v1.d", "secring.*",
    "trustdb.gpg", "hosts.yml", "auth.json", "*recently-used*", "trash",
    # Chromium, Chrome, Brave, Vivaldi, Edge
    "cookies", "cookies-journal", "extension cookies*", "login data*", "web data*", "local state",
    "visited links", "top sites*", "shortcuts*", "favicons*", "network action predictor*",
    "network persistent state", "transportsecurity", "trust tokens*", "sessions", "current session",
    "current tabs", "last session", "last tabs", "session storage", "local storage", "indexeddb",
    "service worker", "sync data", "gcm store", "quotamanager*", "media history*",
    # Firefox, Thunderbird
    "cookies.sqlite*", "logins.json", "logins-backup.json", "key3.db", "key4.db", "cert8.db", "cert9.db",
    "places.sqlite*", "formhistory.sqlite*", "sessionstore*", "sessionstore-backups", "signedinuser.json",
    "webappsstore.sqlite*", "storage", "permissions.sqlite", "content-prefs.sqlite",
)
# Folders that are nothing but keys and passwords.
SECRET_FOLDERS = {".ssh", ".gnupg", ".password-store", "keyrings", ".pki", ".aws", ".kube", ".docker", "gh"}


def _private(_dir, names):
    import fnmatch
    return {n for n in names if any(fnmatch.fnmatchcase(n.lower(), pat) for pat in PRIVATE)}


def _skel_mode(path):
    """Settings stay as private as they were: a file only its owner could read stays so (in /etc/skel
    it would otherwise be readable by every user of the system)."""
    mode = path.lstat().st_mode
    public = mode & 0o044
    if path.is_dir():
        return 0o755 if public else 0o700
    exe = mode & 0o100
    return (0o755 if exe else 0o644) if public else (0o700 if exe else 0o600)


def import_config(project, folder, into=".config"):
    """Copy a settings folder of this computer (for example ~/.config/xfce4) into /etc/skel/<into>/."""
    import os
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Not a folder: {}".format(folder))
    if folder.name.lower() in SECRET_FOLDERS:
        raise ValueError("{} holds keys or passwords: it is not copied into every new user's home".format(folder))
    if not re.match(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$", into) or ".." in into.split("/"):
        raise ValueError("Invalid place in /etc/skel: {}".format(into))
    rootfs = Path(project.rootfs)
    base = resolve_in_root(rootfs, "etc/skel/" + into)
    root = os.path.realpath(str(rootfs)).rstrip("/") + "/"
    if base is None or not os.path.realpath(str(base)).startswith(root):
        raise ValueError("/etc/skel/{} leads out of the system".format(into))
    base.mkdir(parents=True, exist_ok=True)
    dest = base / folder.name
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)
    # Caches, sessions, passwords and keys of this computer stay here.
    shutil.copytree(folder, dest, symlinks=True, ignore=_private)
    for top, dirs, files in os.walk(str(dest)):
        for p in [Path(top)] + [Path(top, n) for n in dirs + files]:
            try:
                if not p.is_symlink():
                    p.chmod(_skel_mode(p))
            except OSError:
                pass
    project.record("skel-import", "{} -> /etc/skel/{}/{}".format(folder, into, folder.name))
    return dest


# GRUB of installed systems --------------------------------------------------------------------------------
def set_grub_background(project, image):
    """GRUB_BACKGROUND for computers installed from the ISO (the installer runs update-grub)."""
    from disco.core import imaging
    rootfs = Path(project.rootfs)
    target = rootfs / "usr/share/images/{}/grub-background.png".format(project.os_id())
    imaging.write_png(image, target, (1920, 1080), fit="cover")
    target.chmod(0o644)
    dropin = rootfs / GRUB_DROPIN
    dropin.parent.mkdir(parents=True, exist_ok=True)
    dropin.write_text("# The GRUB background of installed systems (D!sco)\nGRUB_BACKGROUND=\"/{}\"\n".format(
        target.relative_to(rootfs)))
    # A system that already has GRUB set up gets the new menu now.
    if (rootfs / "boot/grub/grub.cfg").exists() and (rootfs / "usr/sbin/update-grub").exists():
        from disco.core.chroot import Chroot
        with Chroot(rootfs) as ch:
            ch.run(["update-grub"], check=False)
    project.record("grub-background", Path(image).name)
    return target


def clear_grub_background(project):
    p = Path(project.rootfs) / GRUB_DROPIN
    if p.exists():
        p.unlink()
