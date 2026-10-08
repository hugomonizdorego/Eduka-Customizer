"""Identity and look of the image: os-release, Plymouth, wallpaper, login."""

import configparser
import os
import re
import shutil
import tarfile
import zipfile
from pathlib import Path

from eduka_customizer.core.apt import Packages
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.distro import format_os_release, parse_os_release, resolve_in_root
from eduka_customizer.core import fsutil
from eduka_customizer.core.config import DEFAULT_TIMEZONE
from eduka_customizer.core.log import log

BACKGROUNDS = "usr/share/backgrounds/{id}"
PLYMOUTH_THEMES = "usr/share/plymouth/themes"
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HOSTNAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
USERNAME = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def _ini_set(path, section, values, preserve_case=True):
    path = Path(path)
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    if preserve_case:
        cp.optionxform = str
    if path.exists():
        cp.read(path, encoding="utf-8")
    if not cp.has_section(section):
        cp.add_section(section)
    for k, v in values.items():
        cp.set(section, k, str(v))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        cp.write(fh, space_around_delimiters=False)


class Branding:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.chroot = Chroot(project.rootfs)

    # os-release ----------------------------------------------------------
    def os_release(self):
        p = resolve_in_root(self.rootfs, "etc/os-release")
        return parse_os_release(p.read_text()) if p and p.is_file() else {}

    def apply_identity(self, ident, protect=True):
        """Write os-release, issue, hostname and live-config defaults."""
        name = (ident.get("name") or "").strip()
        if not name:
            raise ValueError("Enter the name of your distribution first (Identity page)")
        version = ident.get("version", "")
        codename = ident.get("codename", "")
        os_id = (ident.get("id") or re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-")) or "linux").lower()
        if not SAFE.match(os_id):
            raise ValueError("Invalid OS ID: {}".format(os_id))
        old = self.os_release()
        info = self.project.distro
        debian_code = info.debian_codename or old.get("VERSION_CODENAME", "")
        data = {
            "PRETTY_NAME": "{} {}{}".format(name, version, " ({})".format(codename) if codename else "").strip(),
            "NAME": name,
            "VERSION_ID": version,
            "VERSION": "{}{}".format(version, " ({})".format(codename) if codename else ""),
            # Keep the Debian codename: APT tooling and third-party installers rely on it.
            "VERSION_CODENAME": debian_code,
            "DISTRO_CODENAME": codename,
            "DEBIAN_SUITE": info.suite,
            "ID": os_id,
            "ID_LIKE": "debian",
            "HOME_URL": ident.get("home_url", ""),
            "SUPPORT_URL": ident.get("support_url", ""),
            "BUG_REPORT_URL": ident.get("bug_url", ""),
        }
        data = {k: v for k, v in data.items() if v}
        target = self.rootfs / "usr/lib/os-release"
        if protect:
            self._divert("/usr/lib/os-release")
        target.write_text(format_os_release(data))
        etc = self.rootfs / "etc/os-release"
        if not etc.is_symlink():
            if etc.exists():
                etc.unlink()
            etc.symlink_to("../usr/lib/os-release")
        issue = "{} \\n \\l\n\n".format(data["PRETTY_NAME"])
        (self.rootfs / "etc/issue").write_text(issue)
        (self.rootfs / "etc/issue.net").write_text(data["PRETTY_NAME"] + "\n")
        lsb = self.rootfs / "etc/lsb-release"
        lsb.write_text('DISTRIB_ID="{}"\nDISTRIB_RELEASE="{}"\nDISTRIB_CODENAME="{}"\n'
                       'DISTRIB_DESCRIPTION="{}"\n'.format(name, version, debian_code, data["PRETTY_NAME"]))
        self.set_hostname(ident.get("hostname") or os_id)
        from eduka_customizer.core.users import Users
        live = Users(self.project).live()
        # Keep the live user chosen on the Users page unless the caller names one.
        self.set_live_user(ident.get("live_user") or live["username"],
                           ident.get("live_fullname") or live["fullname"], ident.get("hostname") or os_id)
        self.project.state["identity"].update(ident)
        self.project.record("identity", data["PRETTY_NAME"])
        log.info("Identity set to %s", data["PRETTY_NAME"])

    def _divert(self, path):
        """Keep base-files upgrades from overwriting our branding."""
        out = self.chroot.output(["dpkg-divert", "--list", path], check=False)
        if "local diversion" in out or "diversion of" in out:
            return
        self.chroot.run(["dpkg-divert", "--local", "--no-rename", "--divert", path + ".debian",
                         "--add", path], check=False, quiet=True)
        src = self.rootfs / path.lstrip("/")
        dst = self.rootfs / (path.lstrip("/") + ".debian")
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    def set_hostname(self, hostname):
        if not HOSTNAME.match(hostname):
            raise ValueError("Invalid hostname: {}".format(hostname))
        (self.rootfs / "etc/hostname").write_text(hostname + "\n")
        hosts = self.rootfs / "etc/hosts"
        text = hosts.read_text() if hosts.exists() else "127.0.0.1\tlocalhost\n"
        text = re.sub(r"(?m)^127\.0\.1\.1\s.*\n?", "", text)
        lines = text.rstrip("\n").split("\n")
        lines.insert(1, "127.0.1.1\t{}".format(hostname))
        hosts.write_text("\n".join(lines) + "\n")

    def set_live_user(self, username, fullname, hostname):
        """Name of the live user; the password and groups set on the Users page are kept."""
        from eduka_customizer.core.users import Users
        u = Users(self.project)
        cur = u.live()
        u.set_live(username, fullname, autologin=cur["autologin"], groups=cur["groups"], hostname=hostname,
                   keep_password=True)

    # Locale --------------------------------------------------------------
    def apply_locale(self, default, extra=(), timezone=DEFAULT_TIMEZONE, keyboard="us", variant=""):
        locales = [default] + [l for l in extra if l and l != default]
        supported = self.rootfs / "usr/share/i18n/SUPPORTED"
        valid = set()
        if supported.exists():
            valid = {l.split()[0] for l in supported.read_text().splitlines() if l.strip()}
        bad = [l for l in locales if valid and l not in valid]
        if bad:
            raise ValueError("Unknown locale(s): {}".format(", ".join(bad)))
        if not re.match(r"^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$", timezone):
            raise ValueError("Unknown time zone: {}".format(timezone))
        if not re.match(r"^[a-z]{2,8}(,[a-z]{2,8})*$", keyboard):
            raise ValueError("Invalid keyboard layout: {}".format(keyboard))
        if not re.match(r"^[a-z0-9_,-]*$", variant or ""):
            raise ValueError("Invalid keyboard variant: {}".format(variant))
        with self.chroot:
            missing = [pkg for pkg, path in (("locales", "usr/sbin/locale-gen"), ("tzdata", "usr/share/zoneinfo/UTC"))
                       if not (self.rootfs / path).exists()]
            if missing:
                Packages(self.project).install(missing)
            if not (self.rootfs / "usr/share/zoneinfo" / timezone).exists():
                raise ValueError("Unknown time zone: {}".format(timezone))
            gen = self.rootfs / "etc/locale.gen"
            charmap = {l: (l.split(".")[1] if "." in l else "UTF-8") for l in locales}
            gen.write_text("# Generated by Eduka-Customizer\n" +
                           "".join("{} {}\n".format(l, charmap[l]) for l in locales))
            self.chroot.run(["locale-gen"])
            (self.rootfs / "etc/default/locale").write_text("LANG={}\n".format(default))
            (self.rootfs / "etc/timezone").write_text(timezone + "\n")
            lt = self.rootfs / "etc/localtime"
            if lt.exists() or lt.is_symlink():
                lt.unlink()
            lt.symlink_to("/usr/share/zoneinfo/" + timezone)
            kb = self.rootfs / "etc/default/keyboard"
            text = kb.read_text() if kb.exists() else 'XKBMODEL="pc105"\nXKBVARIANT=""\nXKBOPTIONS=""\nBACKSPACE="guess"\n'
            if re.search(r"(?m)^XKBLAYOUT=", text):
                text = re.sub(r'(?m)^XKBLAYOUT=.*$', 'XKBLAYOUT="{}"'.format(keyboard), text)
            else:
                text += 'XKBLAYOUT="{}"\n'.format(keyboard)
            if re.search(r"(?m)^XKBVARIANT=", text):
                text = re.sub(r'(?m)^XKBVARIANT=.*$', 'XKBVARIANT="{}"'.format(variant or ""), text)
            else:
                text += 'XKBVARIANT="{}"\n'.format(variant or "")
            if "," in keyboard and not re.search(r'(?m)^XKBOPTIONS=".*grp:', text):
                # Several layouts: Alt+Shift switches between them.
                text = re.sub(r'(?m)^XKBOPTIONS="([^"]*)"',
                              lambda m: 'XKBOPTIONS="{}"'.format(",".join(filter(None, [m.group(1), "grp:alt_shift_toggle"]))),
                              text)
            kb.write_text(text)
        conf = self.rootfs / "etc/live/config.conf.d/40-eduka-customizer-locale.conf"
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text('LIVE_LOCALES="{}"\nLIVE_TIMEZONE="{}"\nLIVE_KEYBOARD_LAYOUTS="{}"\n'
                        'LIVE_KEYBOARD_VARIANTS="{}"\n'.format(",".join(locales), timezone, keyboard,
                                                               variant or ""))
        self.project.state["locale"] = {"default": default, "extra": list(extra),
                                        "timezone": timezone, "keyboard": keyboard, "variant": variant or ""}
        self.project.record("locale", default)

    def timezones(self):
        base = self.rootfs / "usr/share/zoneinfo"
        tab = base / "tzdata.zi"
        zones = []
        zone1970 = base / "zone1970.tab"
        if zone1970.exists():
            for line in zone1970.read_text().splitlines():
                if line and not line.startswith("#"):
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        zones.append(parts[2])
        elif tab.exists():
            zones = re.findall(r"(?m)^Z (\S+)", tab.read_text())
        return sorted(set(zones + ["UTC"]))

    def supported_locales(self):
        p = self.rootfs / "usr/share/i18n/SUPPORTED"
        if not p.exists():
            return ["C.UTF-8", "en_US.UTF-8"]
        return [l.split()[0] for l in p.read_text().splitlines() if "UTF-8" in l]

    # Plymouth --------------------------------------------------------------
    def plymouth_themes(self):
        d = self.rootfs / PLYMOUTH_THEMES
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir() if (p / (p.name + ".plymouth")).exists()
                      or any(p.glob("*.plymouth")))

    def plymouth_current(self):
        conf = self.rootfs / "etc/plymouth/plymouthd.conf"
        if conf.exists():
            m = re.search(r"(?m)^Theme=(\S+)", conf.read_text())
            if m:
                return m.group(1)
        default = self.rootfs / "usr/share/plymouth/themes/default.plymouth"
        if default.exists():
            m = re.search(r"(?m)^ImageDir=.*/themes/([^/\s]+)", default.read_text(errors="replace"))
            if m:
                return m.group(1)
        return ""

    def ensure_plymouth(self):
        if not any((self.rootfs / d / "plymouthd").exists() for d in ("usr/sbin", "sbin")):
            Packages(self.project).install(["plymouth", "plymouth-themes", "plymouth-label"])

    def write_plymouth_default(self, theme):
        """Select *theme* without rebuilding anything.

        Debian has plymouth-set-default-theme; where it is missing (or not
        executable) plymouthd.conf is written directly, which plymouthd reads first.
        """
        tool = self.rootfs / "usr/sbin/plymouth-set-default-theme"
        if tool.is_file() and os.access(tool, os.X_OK) and tool.stat().st_size:
            self.chroot.run(["plymouth-set-default-theme", theme])
            return
        conf = self.rootfs / "etc/plymouth/plymouthd.conf"
        conf.parent.mkdir(parents=True, exist_ok=True)
        if not conf.exists():
            conf.write_text("[Daemon]\n")
        _ini_set(conf, "Daemon", {"Theme": theme})

    def set_plymouth(self, theme):
        if not SAFE.match(theme):
            raise ValueError("Invalid theme name")
        with self.chroot:
            self.ensure_plymouth()
            if theme not in self.plymouth_themes():
                raise ValueError("Plymouth theme not installed: {}".format(theme))
            self.write_plymouth_default(theme)
        self._grub_default_splash()
        self.project.mark_initramfs_dirty()
        self.project.record("plymouth", theme)
        log.info("Plymouth theme: %s (initramfs will be rebuilt)", theme)

    def _grub_default_splash(self):
        """Make the installed system boot with 'quiet splash'."""
        p = self.rootfs / "etc/default/grub"
        if not p.exists():
            return
        text = p.read_text()
        m = re.search(r'(?m)^GRUB_CMDLINE_LINUX_DEFAULT="([^"]*)"', text)
        if m:
            opts = m.group(1).split()
            for o in ("quiet", "splash"):
                if o not in opts:
                    opts.append(o)
            text = text[:m.start(1)] + " ".join(opts) + text[m.end(1):]
            p.write_text(text)

    def import_plymouth(self, source, theme=None):
        """Import a theme from a directory, .tar.* or .zip archive.

        *theme* picks one theme when the source holds several (a chosen .plymouth file).
        """
        source = Path(source)
        if source.is_dir() and theme:
            size = sum(f.stat().st_size for f in source.rglob("*") if f.is_file() and not f.is_symlink())
            if size > 200 * 1024 ** 2:
                raise ValueError("{} is very large ({} MiB): put the theme in a folder of its own".format(
                    source, size // 1024 ** 2))
        dest_root = self.rootfs / PLYMOUTH_THEMES
        dest_root.mkdir(parents=True, exist_ok=True)
        tmp = self.project.cache / "plymouth-import"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        if source.is_dir():
            fsutil.copytree(source, tmp / source.name)
        elif tarfile.is_tarfile(source):
            with tarfile.open(source) as tf:
                for member in tf.getmembers():
                    if member.name.startswith("/") or ".." in Path(member.name).parts \
                            or member.isdev() or member.islnk():
                        raise ValueError("Unsafe entry in archive: {}".format(member.name))
                try:
                    tf.extractall(tmp, filter="data")
                except TypeError:  # Python < 3.11.4
                    tf.extractall(tmp)
        elif zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as zf:
                for member in zf.namelist():
                    if member.startswith("/") or ".." in Path(member).parts:
                        raise ValueError("Unsafe path in archive: {}".format(member))
                zf.extractall(tmp)
        else:
            raise ValueError("Unsupported theme source: {}".format(source))
        found = sorted(tmp.rglob("*.plymouth"))
        if theme:
            found = [f for f in found if f.stem == theme and f.parent == tmp / source.name] or \
                [f for f in found if f.stem == theme]
        if not found:
            raise ValueError("No .plymouth file found in {}".format(source))
        theme_dir = found[0].parent
        name = found[0].stem
        if not SAFE.match(name):
            raise ValueError("Invalid theme name: {}".format(name))
        target = dest_root / name
        if target.exists():
            shutil.rmtree(target)
        fsutil.copytree(theme_dir, target)
        # Fix ImageDir/ScriptFile paths to the installed location.
        pf = target / (name + ".plymouth")
        text = pf.read_text(errors="replace")
        text = re.sub(r"(?m)^(ImageDir=).*$", r"\g<1>/usr/share/plymouth/themes/" + name, text)
        text = re.sub(r"(?m)^(ScriptFile=)(?:.*/)?([^/\n]+)$",
                      r"\g<1>/usr/share/plymouth/themes/" + name + r"/\2", text)
        pf.write_text(text)
        shutil.rmtree(tmp, ignore_errors=True)
        log.info("Imported Plymouth theme %s", name)
        return name

    def generate_plymouth(self, name, logo, background="#0b3d2e", spinner_color="#00a879"):
        """Create a simple script theme: centered logo, progress bar."""
        if not SAFE.match(name):
            raise ValueError("Invalid theme name")
        for c in (background, spinner_color):
            if not re.match(r"^#[0-9a-fA-F]{6}$", c):
                raise ValueError("Colors must look like #RRGGBB")
        target = self.rootfs / PLYMOUTH_THEMES / name
        target.mkdir(parents=True, exist_ok=True)
        from eduka_customizer.core import imaging
        imaging.write_png(logo, target / "logo.png")
        bg = [int(background[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        fg = [int(spinner_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        (target / (name + ".plymouth")).write_text(
            "[Plymouth Theme]\nName={0}\nDescription=Boot splash generated by "
            "Eduka-Customizer\nModuleName=script\n\n[script]\nImageDir=/usr/share/plymouth/themes/{0}\n"
            "ScriptFile=/usr/share/plymouth/themes/{0}/{0}.script\n".format(name))
        (target / (name + ".script")).write_text(PLYMOUTH_SCRIPT % {
            "r": bg[0], "g": bg[1], "b": bg[2], "fr": fg[0], "fg": fg[1], "fb": fg[2]})
        self._write_bar(target, spinner_color)
        log.info("Generated Plymouth theme %s", name)
        return name

    def _write_bar(self, target, color):
        """Write a 1x1 PNG pixel used to draw the progress bar."""
        import struct
        import zlib
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))

        def chunk(kind, data):
            c = struct.pack(">I", len(data)) + kind + data
            return c + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + \
            chunk(b"IDAT", zlib.compress(bytes([0, r, g, b]))) + chunk(b"IEND", b"")
        (target / "bar.png").write_bytes(png)

    # Wallpaper ---------------------------------------------------------------
    def set_wallpaper(self, image):
        image = Path(image)
        if image.suffix.lower() not in (".png", ".jpg", ".jpeg", ".svg", ".webp"):
            raise ValueError("Wallpaper must be PNG, JPEG, SVG or WebP")
        try:
            # A picture of the wallpaper gallery is already in the image: use it as it is.
            dest = self.rootfs / image.resolve().relative_to(self.rootfs.resolve())
        except ValueError:
            dest_dir = self.rootfs / BACKGROUNDS.format(id=self.project.os_id())
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / ("wallpaper" + image.suffix.lower())
            shutil.copy2(image, dest)
        path = "/" + str(dest.relative_to(self.rootfs))
        # LXQt / Eduka-Desktop (pcmanfm-qt)
        for rel in ("etc/xdg/pcmanfm-qt/lxqt/settings.conf", "etc/skel/.config/pcmanfm-qt/lxqt/settings.conf"):
            p = self.rootfs / rel
            if rel.startswith("etc/xdg") or p.exists() or (self.rootfs / "usr/bin/pcmanfm-qt").exists():
                _ini_set(p, "Desktop", {"Wallpaper": path, "WallpaperMode": "zoom"})
        # GNOME, Cinnamon, MATE, Budgie (gsettings overrides)
        override = self.rootfs / "usr/share/glib-2.0/schemas/90_eduka-customizer-wallpaper.gschema.override"
        override.parent.mkdir(parents=True, exist_ok=True)
        uri = "file://" + path
        override.write_text(
            "[org.gnome.desktop.background]\npicture-uri='{0}'\npicture-uri-dark='{0}'\n\n"
            "[org.cinnamon.desktop.background]\npicture-uri='{0}'\n\n"
            "[org.mate.background]\npicture-filename='{1}'\n".format(uri, path))
        if (self.rootfs / "usr/bin/glib-compile-schemas").exists():
            self.chroot.run(["glib-compile-schemas", "/usr/share/glib-2.0/schemas"], check=False, quiet=True)
        # Xfce
        xfce = self.rootfs / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
        if (self.rootfs / "usr/bin/xfdesktop").exists():
            xfce.parent.mkdir(parents=True, exist_ok=True)
            xfce.write_text(XFCE_DESKTOP % {"path": path})
        # KDE Plasma
        plasma = self.rootfs / "usr/share/plasma/look-and-feel"
        if plasma.is_dir():
            for defaults in plasma.glob("*/contents/defaults"):
                _ini_set(defaults, "Wallpaper", {"Image": path})
        # Debian desktop-base alternative
        if (self.rootfs / "usr/share/images/desktop-base").is_dir():
            self.chroot.run(["update-alternatives", "--install",
                             "/usr/share/images/desktop-base/desktop-background",
                             "desktop-background", path, "90"], check=False, quiet=True)
            self.chroot.run(["update-alternatives", "--set", "desktop-background", path],
                            check=False, quiet=True)
        self.project.record("wallpaper", path)
        log.info("Default wallpaper: %s", path)
        return path

    # Login screen -------------------------------------------------------------
    def login_themes(self):
        d = self.rootfs / "usr/share/sddm/themes"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def gtk_themes(self):
        d = self.rootfs / "usr/share/themes"
        return sorted(p.name for p in d.iterdir() if (p / "gtk-3.0").is_dir()) if d.is_dir() else []

    def icon_themes(self):
        d = self.rootfs / "usr/share/icons"
        return sorted(p.name for p in d.iterdir() if (p / "index.theme").exists()) if d.is_dir() else []

    def set_login_screen(self, background=None, gtk_theme="", icon_theme="", sddm_theme="",
                         font="", greeter_logo=None):
        from eduka_customizer.core.desktop import detect_display_manager
        dm = detect_display_manager(self.rootfs)
        bg_path = ""
        if background:
            dest_dir = self.rootfs / BACKGROUNDS.format(id=self.project.os_id())
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / ("login" + Path(background).suffix.lower())
            shutil.copy2(background, dest)
            bg_path = "/" + str(dest.relative_to(self.rootfs))
        logo_path = ""
        if greeter_logo:
            dest = self.rootfs / BACKGROUNDS / ("logo" + Path(greeter_logo).suffix.lower())
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(greeter_logo, dest)
            logo_path = "/" + str(dest.relative_to(self.rootfs))
        log.info("Configuring login screen for %s", dm or "no display manager")
        if dm == "lightdm" or (self.rootfs / "usr/sbin/lightdm").exists():
            values = {}
            if bg_path:
                values["background"] = bg_path
            if gtk_theme:
                values["theme-name"] = gtk_theme
            if icon_theme:
                values["icon-theme-name"] = icon_theme
            if font:
                values["font-name"] = font
            if logo_path:
                values["default-user-image"] = logo_path
            if values:
                if (self.rootfs / "usr/sbin/lightdm-gtk-greeter").exists():
                    _ini_set(self.rootfs / "etc/lightdm/lightdm-gtk-greeter.conf.d/50-eduka-customizer.conf",
                             "greeter", values)
                if (self.rootfs / "usr/sbin/slick-greeter").exists():
                    slick = {"background": bg_path} if bg_path else {}
                    if gtk_theme:
                        slick["theme-name"] = gtk_theme
                    if icon_theme:
                        slick["icon-theme-name"] = icon_theme
                    if logo_path:
                        slick["logo"] = logo_path
                    _ini_set(self.rootfs / "etc/lightdm/slick-greeter.conf", "Greeter", slick)
        if dm == "sddm" or (self.rootfs / "usr/bin/sddm").exists():
            if sddm_theme:
                _ini_set(self.rootfs / "etc/sddm.conf.d/10-eduka-customizer-theme.conf", "Theme",
                         {"Current": sddm_theme})
            theme = sddm_theme or self._sddm_current()
            if bg_path and theme and (self.rootfs / "usr/share/sddm/themes" / theme).is_dir():
                _ini_set(self.rootfs / "usr/share/sddm/themes" / theme / "theme.conf.user",
                         "General", {"background": bg_path, "type": "image"})
        if dm == "gdm3" or (self.rootfs / "usr/sbin/gdm3").exists():
            if logo_path:
                (self.rootfs / "usr/share/glib-2.0/schemas/91_eduka-customizer-gdm.gschema.override").write_text(
                    "[org.gnome.login-screen]\nlogo='{}'\n".format(logo_path))
                self.chroot.run(["glib-compile-schemas", "/usr/share/glib-2.0/schemas"],
                                check=False, quiet=True)
            if bg_path:
                log.warning("GDM backgrounds live in the gnome-shell theme resource and are not "
                            "changed; only the logo was applied.")
        if dm == "lxdm" or (self.rootfs / "usr/sbin/lxdm").exists():
            if bg_path:
                _ini_set(self.rootfs / "etc/lxdm/lxdm.conf", "display", {"bg": bg_path}, )
        self.project.record("login-screen", dm)

    def _sddm_current(self):
        for p in sorted((self.rootfs / "etc/sddm.conf.d").glob("*.conf")) + [self.rootfs / "etc/sddm.conf"]:
            if p.exists():
                m = re.search(r"(?ms)^\[Theme\].*?^Current=(\S+)", p.read_text(errors="replace"))
                if m:
                    return m.group(1)
        return "debian-breeze" if (self.rootfs / "usr/share/sddm/themes/debian-breeze").is_dir() else ""

    # Calamares installer branding ------------------------------------------
    def calamares_branding(self, product, version, url=""):
        base = self.rootfs / "etc/calamares/branding"
        if not base.is_dir():
            return False
        changed = False
        # The EFI folder name comes from bootloaderEntryName unless bootloader.conf sets
        # efiBootloaderId: never change it then, or Debian's signed GRUB would not boot.
        boot = self.rootfs / "etc/calamares/modules/bootloader.conf"
        fixed_id = boot.exists() and re.search(r"(?m)^efiBootloaderId:\s*\S", boot.read_text(errors="replace"))
        for desc in base.glob("*/branding.desc"):
            text = desc.read_text(errors="replace")
            for key, value in (("productName", product), ("shortProductName", product),
                               ("version", version), ("shortVersion", version),
                               ("versionedName", "{} {}".format(product, version)),
                               ("shortVersionedName", "{} {}".format(product, version)),
                               ("bootloaderEntryName", product.replace(" ", "") if fixed_id else ""),
                               ("productUrl", url)):
                if value:
                    text = re.sub(r'(?m)^(\s*{}:\s*).*$'.format(key),
                                  lambda m, v=value: m.group(1) + '"{}"'.format(v.replace('"', "'")), text)
            desc.write_text(text)
            changed = True
        return changed


PLYMOUTH_SCRIPT = """# Boot splash (generated by Eduka-Customizer)
Window.SetBackgroundTopColor(%(r).3f, %(g).3f, %(b).3f);
Window.SetBackgroundBottomColor(%(r).3f, %(g).3f, %(b).3f);

logo.image = Image("logo.png");
max_w = Window.GetWidth() * 0.35;
if (logo.image.GetWidth() > max_w) {
    logo.image = logo.image.Scale(max_w, logo.image.GetHeight() * max_w / logo.image.GetWidth());
}
logo.sprite = Sprite(logo.image);
logo.sprite.SetX(Window.GetX() + Window.GetWidth() / 2 - logo.image.GetWidth() / 2);
logo.sprite.SetY(Window.GetY() + Window.GetHeight() / 2 - logo.image.GetHeight() / 2);
logo.sprite.SetOpacity(0);

bar.width = Window.GetWidth() * 0.25;
bar.x = Window.GetX() + Window.GetWidth() / 2 - bar.width / 2;
bar.y = Window.GetY() + Window.GetHeight() / 2 + logo.image.GetHeight() / 2 + 40;
bar.original = Image("bar.png");
bar.sprite = Sprite();
bar.sprite.SetPosition(bar.x, bar.y, 1);

fade = 0;
fun refresh_callback() {
    if (fade < 1) { fade += 0.04; logo.sprite.SetOpacity(fade); }
}
Plymouth.SetRefreshFunction(refresh_callback);

fun progress_callback(duration, progress) {
    w = Math.Int(bar.width * progress);
    if (w < 1) w = 1;
    bar.sprite.SetImage(bar.original.Scale(w, 4));
}
Plymouth.SetBootProgressFunction(progress_callback);

message_sprite = Sprite();
message_sprite.SetPosition(Window.GetX() + 20, Window.GetY() + Window.GetHeight() - 40, 2);
fun message_callback(text) {
    message_sprite.SetImage(Image.Text(text, %(fr).3f, %(fg).3f, %(fb).3f));
}
Plymouth.SetMessageFunction(message_callback);

# Password prompt (encrypted disks)
fun display_password_callback(prompt, bullets) {
    s = prompt + ": ";
    for (i = 0; i < bullets; i++) s += "*";
    message_callback(s);
}
Plymouth.SetDisplayPasswordFunction(display_password_callback);
fun display_normal_callback() { message_sprite.SetImage(Image.Text("", 1, 1, 1)); }
Plymouth.SetDisplayNormalFunction(display_normal_callback);
"""

XFCE_DESKTOP = """<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="backdrop" type="empty">
    <property name="screen0" type="empty">
      <property name="monitorscreen" type="empty">
        <property name="workspace0" type="empty">
          <property name="last-image" type="string" value="%(path)s"/>
          <property name="image-style" type="int" value="5"/>
        </property>
      </property>
      <property name="monitorVirtual-1" type="empty">
        <property name="workspace0" type="empty">
          <property name="last-image" type="string" value="%(path)s"/>
          <property name="image-style" type="int" value="5"/>
        </property>
      </property>
    </property>
  </property>
</channel>
"""
