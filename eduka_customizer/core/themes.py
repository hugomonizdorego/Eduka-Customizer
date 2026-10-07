"""System-wide look: GTK/Qt themes, icons, cursors, fonts, desktop icons.

Defaults are written for every desktop that reads them (GTK 2/3/4,
GNOME/Cinnamon/MATE gsettings, LXQt and Eduka-Desktop, Xfce, KDE) so a
choice made here is what every new user (and the live user) gets.
"""

import configparser
import re
import shutil
import tarfile
import zipfile
from pathlib import Path

from eduka_customizer.core.apt import Packages
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core import fsutil
from eduka_customizer.core.log import log

SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+-]{0,80}$")

# Theme packs offered with one click (availability is checked with APT).
THEME_PACKS = [
    ("papirus-icon-theme", "icons", "Papirus icons"),
    ("numix-icon-theme-circle", "icons", "Numix Circle icons"),
    ("elementary-xfce-icon-theme", "icons", "elementary Xfce icons"),
    ("breeze-icon-theme", "icons", "Breeze icons (KDE)"),
    ("adwaita-icon-theme", "icons", "Adwaita icons (GNOME)"),
    ("yaru-theme-icon", "icons", "Yaru icons"),
    ("arc-theme", "gtk", "Arc GTK theme"),
    ("materia-gtk-theme", "gtk", "Materia GTK theme"),
    ("numix-gtk-theme", "gtk", "Numix GTK theme"),
    ("greybird-gtk-theme", "gtk", "Greybird GTK theme"),
    ("breeze-gtk-theme", "gtk", "Breeze GTK theme"),
    ("yaru-theme-gtk", "gtk", "Yaru GTK theme"),
    ("orchis-gtk-theme", "gtk", "Orchis GTK theme"),
    ("breeze-cursor-theme", "cursor", "Breeze cursors"),
    ("dmz-cursor-theme", "cursor", "DMZ cursors"),
    ("oxygen-cursor-theme", "cursor", "Oxygen cursors"),
    ("fonts-noto", "font", "Noto fonts (many languages)"),
    ("fonts-noto-color-emoji", "font", "Noto color emoji"),
    ("fonts-inter", "font", "Inter"),
    ("fonts-cantarell", "font", "Cantarell"),
    ("fonts-liberation2", "font", "Liberation (MS compatible)"),
    ("qt5ct", "qt", "Qt5 settings (Qt apps follow your choice)"),
    ("qt6ct", "qt", "Qt6 settings"),
    ("picom", "compositor", "picom compositor"),
]


def _ini(path, section, values):
    path = Path(path)
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if path.exists():
        try:
            cp.read(path, encoding="utf-8")
        except configparser.Error:
            pass
    if not cp.has_section(section):
        cp.add_section(section)
    for k, v in values.items():
        cp.set(section, k, str(v))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        cp.write(fh, space_around_delimiters=False)


def _xml_prop(path, name, value):
    """Change a value in an existing xfconf XML file (keeps the rest)."""
    path = Path(path)
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    new, n = re.subn(r'(<property name="{}" type="\w+" value=")[^"]*(")'.format(re.escape(name)),
                     lambda m: m.group(1) + value + m.group(2), text)
    if n:
        path.write_text(new)
    return bool(n)


class Themes:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs

    # Inventory --------------------------------------------------------
    def gtk_themes(self):
        out = set()
        for base in ("usr/share/themes",):
            d = self.rootfs / base
            if d.is_dir():
                out |= {p.name for p in d.iterdir() if (p / "gtk-3.0").is_dir() or (p / "gtk-4.0").is_dir()}
        return sorted(out)

    def icon_themes(self):
        d = self.rootfs / "usr/share/icons"
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir() if (p / "index.theme").exists()
                      and not (p / "cursors").is_dir() and p.name not in ("default", "hicolor", "locolor"))

    def cursor_themes(self):
        d = self.rootfs / "usr/share/icons"
        return sorted(p.name for p in d.iterdir() if (p / "cursors").is_dir()) if d.is_dir() else []

    def lxqt_themes(self):
        d = self.rootfs / "usr/share/lxqt/themes"
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    def kvantum_themes(self):
        d = self.rootfs / "usr/share/Kvantum"
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    def current(self):
        p = self.rootfs / "etc/gtk-3.0/settings.ini"
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read(p)
        except configparser.Error:
            pass
        get = lambda k: cp.get("Settings", k, fallback="")
        cursor = ""
        idx = self.rootfs / "usr/share/icons/default/index.theme"
        if idx.exists():
            m = re.search(r"(?m)^Inherits=(\S+)", idx.read_text(errors="replace"))
            cursor = m.group(1) if m else ""
        return {"gtk": get("gtk-theme-name"), "icons": get("gtk-icon-theme-name"),
                "cursor": cursor or get("gtk-cursor-theme-name"), "font": get("gtk-font-name"),
                "dark": get("gtk-application-prefer-dark-theme") in ("1", "true")}

    # Apply --------------------------------------------------------------
    def apply(self, gtk="", icons="", cursor="", font="", dark=False, lxqt_theme="",
              qt_style="", cursor_size=24):
        for v in (gtk, icons, cursor, font, lxqt_theme, qt_style):
            if v and not SAFE.match(v):
                raise ValueError("Invalid theme name: {}".format(v))
        r = self.rootfs
        gtk_vals = {}
        if gtk:
            gtk_vals["gtk-theme-name"] = gtk
        if icons:
            gtk_vals["gtk-icon-theme-name"] = icons
        if cursor:
            gtk_vals["gtk-cursor-theme-name"] = cursor
            gtk_vals["gtk-cursor-theme-size"] = cursor_size
        if font:
            gtk_vals["gtk-font-name"] = font
        gtk_vals["gtk-application-prefer-dark-theme"] = "1" if dark else "0"
        for rel in ("etc/gtk-3.0/settings.ini", "etc/gtk-4.0/settings.ini"):
            vals = dict(gtk_vals)
            # GTK 4 falls back to Adwaita when the theme has no gtk-4.0 folder.
            if rel.startswith("etc/gtk-4.0") and gtk and not (r / "usr/share/themes" / gtk / "gtk-4.0").is_dir():
                vals.pop("gtk-theme-name", None)
            _ini(r / rel, "Settings", vals)
        gtk2 = []
        if gtk:
            gtk2.append('gtk-theme-name="{}"'.format(gtk))
        if icons:
            gtk2.append('gtk-icon-theme-name="{}"'.format(icons))
        if cursor:
            gtk2.append('gtk-cursor-theme-name="{}"'.format(cursor))
        if font:
            gtk2.append('gtk-font-name="{}"'.format(font))
        if gtk2:
            (r / "etc/skel").mkdir(parents=True, exist_ok=True)
            (r / "etc/skel/.gtkrc-2.0").write_text("\n".join(gtk2) + "\n")
            (r / "etc/gtk-2.0").mkdir(parents=True, exist_ok=True)
            (r / "etc/gtk-2.0/gtkrc").write_text("\n".join(gtk2) + "\n")
        if cursor:
            idx = r / "usr/share/icons/default/index.theme"
            idx.parent.mkdir(parents=True, exist_ok=True)
            idx.write_text("[Icon Theme]\nInherits={}\n".format(cursor))
            (r / "etc/X11/Xresources").mkdir(parents=True, exist_ok=True)
            (r / "etc/X11/Xresources/90-eduka-cursor").write_text(
                "Xcursor.theme: {}\nXcursor.size: {}\n".format(cursor, cursor_size))
        # gsettings (GNOME, Cinnamon, MATE, Budgie)
        over = []
        iface = []
        if gtk:
            iface.append("gtk-theme='{}'".format(gtk))
        if icons:
            iface.append("icon-theme='{}'".format(icons))
        if cursor:
            iface.append("cursor-theme='{}'".format(cursor))
        if font:
            iface.append("font-name='{}'".format(font))
        iface.append("color-scheme='{}'".format("prefer-dark" if dark else "default"))
        over.append("[org.gnome.desktop.interface]\n" + "\n".join(iface))
        over.append("[org.cinnamon.desktop.interface]\n" + "\n".join(i for i in iface if not i.startswith("color")))
        mate = [i for i in iface if i.startswith(("gtk-theme", "icon-theme", "font-name"))]
        if mate:
            over.append("[org.mate.interface]\n" + "\n".join(mate))
        schemas = r / "usr/share/glib-2.0/schemas"
        schemas.mkdir(parents=True, exist_ok=True)
        (schemas / "91_eduka-theme.gschema.override").write_text("\n\n".join(over) + "\n")
        if (r / "usr/bin/glib-compile-schemas").exists():
            Chroot(r).run(["glib-compile-schemas", "/usr/share/glib-2.0/schemas"], check=False, quiet=True)
        # LXQt and Eduka-Desktop
        lx = {}
        if icons:
            lx["icon_theme"] = icons
        if lxqt_theme:
            lx["theme"] = lxqt_theme
        if lx:
            _ini(r / "etc/xdg/lxqt/lxqt.conf", "General", lx)
        if qt_style:
            _ini(r / "etc/xdg/lxqt/lxqt.conf", "Qt", {"style": qt_style})
        if cursor:
            _ini(r / "etc/xdg/lxqt/session.conf", "Mouse", {"cursor_theme": cursor, "cursor_size": cursor_size})
        # Xfce
        xs = r / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
        if gtk:
            _xml_prop(xs, "ThemeName", gtk)
        if icons:
            _xml_prop(xs, "IconThemeName", icons)
        if cursor:
            _xml_prop(xs, "CursorThemeName", cursor)
        if font:
            _xml_prop(xs, "FontName", font)
        # KDE Plasma
        if icons:
            _ini(r / "etc/xdg/kdeglobals", "Icons", {"Theme": icons})
        if cursor:
            _ini(r / "etc/xdg/kcminputrc", "Mouse", {"cursorTheme": cursor})
        self.project.state["themes"] = {"gtk": gtk, "icons": icons, "cursor": cursor, "font": font,
                                        "dark": dark, "lxqt": lxqt_theme, "qt_style": qt_style}
        self.project.record("themes", ", ".join(v for v in (gtk, icons, cursor, font) if v))
        log.info("System theme: GTK %s, icons %s, cursor %s, font %s", gtk or "-", icons or "-",
                 cursor or "-", font or "-")

    def desktop_icons(self, home=True, trash=True, computer=True, network=False):
        """Icons on the desktop for LXQt/Eduka-Desktop (pcmanfm-qt) and Xfce."""
        names = [n for n, on in (("Home", home), ("Trash", trash), ("Computer", computer),
                                 ("Network", network)) if on]
        _ini(self.rootfs / "etc/xdg/pcmanfm-qt/lxqt/settings.conf", "Desktop",
             {"DesktopShortcuts": ", ".join(names)})
        xd = self.rootfs / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
        for prop, on in (("show-home", home), ("show-trash", trash), ("show-filesystem", computer)):
            _xml_prop(xd, prop, "true" if on else "false")
        self.project.record("desktop-icons", ",".join(names))

    # Install ------------------------------------------------------------
    def install_packs(self, packages):
        pk = Packages(self.project)
        with pk.chroot:
            pk.update()
            ok = pk.available(packages)
            missing = [p for p in packages if p not in ok]
            if missing:
                log.warning("Not available for this Debian suite: %s", " ".join(missing))
            if ok:
                pk.install(sorted(ok), update=False)
        return sorted(ok), missing

    def import_theme(self, source):
        """Import a theme folder or archive into /usr/share/themes or /usr/share/icons."""
        source = Path(source)
        tmp = self.project.cache / "theme-import"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        if source.is_dir():
            fsutil.copytree(source, tmp / source.name, symlinks=True)
        elif tarfile.is_tarfile(source):
            with tarfile.open(source) as tf:
                for m in tf.getmembers():
                    if m.name.startswith("/") or ".." in Path(m.name).parts or m.isdev() or m.islnk():
                        raise ValueError("Unsafe entry in archive: {}".format(m.name))
                    if m.issym() and (m.linkname.startswith("/") or ".." in Path(m.linkname).parts):
                        raise ValueError("Unsafe link in archive: {}".format(m.name))
                try:
                    tf.extractall(tmp, filter="data")
                except TypeError:
                    tf.extractall(tmp)
        elif zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as zf:
                for n in zf.namelist():
                    if n.startswith("/") or ".." in Path(n).parts:
                        raise ValueError("Unsafe path in archive: {}".format(n))
                zf.extractall(tmp)
        else:
            raise ValueError("Unsupported theme file: {}".format(source))
        imported = []
        for index in tmp.rglob("index.theme"):
            d = index.parent
            kind = "icons" if ((d / "cursors").is_dir() or "[Icon Theme]" in index.read_text(errors="replace")) \
                else "themes"
            if kind == "themes" and not any((d / x).is_dir() for x in ("gtk-2.0", "gtk-3.0", "gtk-4.0", "xfwm4", "openbox-3")):
                continue
            dest = self.rootfs / "usr/share" / kind / d.name
            if dest.exists():
                shutil.rmtree(dest)
            fsutil.copytree(d, dest, symlinks=True)
            imported.append("{} ({})".format(d.name, "icons" if kind == "icons" else "theme"))
        for gtkdir in tmp.rglob("gtk-3.0"):
            d = gtkdir.parent
            dest = self.rootfs / "usr/share/themes" / d.name
            if not dest.exists():
                fsutil.copytree(d, dest, symlinks=True)
                imported.append("{} (theme)".format(d.name))
        shutil.rmtree(tmp, ignore_errors=True)
        if not imported:
            raise ValueError("No GTK theme, icon theme or cursor theme found in {}".format(source))
        if (self.rootfs / "usr/bin/gtk-update-icon-cache").exists():
            Chroot(self.rootfs).run(["sh", "-c", "for d in /usr/share/icons/*/; do "
                                     "[ -f \"$d/index.theme\" ] && gtk-update-icon-cache -q -f \"$d\"; done; true"],
                                    check=False, quiet=True)
        self.project.record("theme-import", ", ".join(imported))
        log.info("Imported: %s", ", ".join(imported))
        return imported
