"""About page: version, license, credits, the licenses of every component,
trademarks, the user guide and ways to support the project."""

import os
import pwd
import shutil
import subprocess
from pathlib import Path

from eduka_customizer import (APP_NAME, AUTHOR, DONATE_URL, FACEBOOK_URL, HOMEPAGE, LICENSE, OLD_NAME,
                              VERSION_LABEL)
from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import QDialog, QLabel, QPlainTextEdit, QVBoxLayout

from eduka_customizer.gui.widgets import Page, button, fill, hbox, label, table

# (component, what DistroForge uses it for, license, home page)
COMPONENTS = [
    ("Python", "programming language", "PSF-2.0", "python.org"),
    ("PyQt6 / PyQt5", "window toolkit binding", "GPL-3.0", "riverbankcomputing.com"),
    ("Qt 6 / Qt 5", "window toolkit", "LGPL-3.0 / GPL", "qt.io"),
    ("PyYAML", "Calamares configuration files", "MIT", "pyyaml.org"),
    ("Papirus icon theme", "menu icons (bundled)", "GPL-3.0", "github.com/PapirusDevelopmentTeam"),
    ("squashfs-tools", "compressing the live system", "GPL-2.0-or-later", "github.com/plougher/squashfs-tools"),
    ("xorriso (libisoburn)", "writing the ISO image", "GPL-3.0-or-later", "gnu.org/software/xorriso"),
    ("mtools, dosfstools", "the UEFI boot image", "GPL-3.0-or-later", "gnu.org/software/mtools"),
    ("SYSLINUX / ISOLINUX", "BIOS boot menu of the ISO", "GPL-2.0-or-later", "syslinux.org"),
    ("GNU GRUB", "UEFI boot menu, installed systems", "GPL-3.0-or-later", "gnu.org/software/grub"),
    ("shim", "Secure Boot", "BSD-2-Clause", "github.com/rhboot/shim"),
    ("systemd-boot", "optional boot loader", "LGPL-2.1-or-later", "systemd.io"),
    ("rEFInd", "optional boot loader", "GPL-3.0-or-later", "rodsbooks.com/refind"),
    ("live-boot, live-config", "starting the live system", "GPL-3.0-or-later", "salsa.debian.org/live-team"),
    ("Calamares", "the graphical installer", "GPL-3.0-or-later", "calamares.io"),
    ("mmdebstrap / debootstrap", "new Debian base systems", "MIT", "gitlab.mister-muffin.de/josch/mmdebstrap"),
    ("APT, dpkg", "packages inside the image", "GPL-2.0-or-later", "debian.org"),
    ("Flatpak", "Flathub applications", "LGPL-2.1-or-later", "flatpak.org"),
    ("Plymouth", "boot splash", "GPL-2.0-or-later", "freedesktop.org"),
    ("QEMU", "testing the ISO", "GPL-2.0", "qemu.org"),
    ("OVMF (EDK II)", "UEFI firmware for tests", "BSD-2-Clause-Patent", "tianocore.org"),
    ("Xephyr (X.Org)", "live session in a window", "MIT / X11", "x.org"),
    ("GTK 3, PyGObject", "the welcome screen in the ISO", "LGPL-2.1-or-later", "gtk.org"),
    ("freedesktop sound theme", "standard event sounds", "GPL-2.0-or-later / CC-BY-SA", "freedesktop.org"),
    ("Eduka-Desktop", "optional desktop (built from its repository)", "see its repository",
     "github.com/hugomonizdorego/Eduka-Desktop"),
]

TRADEMARKS = (
    "Debian is a registered trademark of Software in the Public Interest, Inc. "
    "Linux® is the registered trademark of Linus Torvalds in the U.S. and other countries. "
    "Ubuntu is a registered trademark of Canonical Ltd. Linux Mint is a trademark of the Linux Mint project. "
    "GNOME is a trademark of the GNOME Foundation. KDE® and Plasma® are registered trademarks of KDE e.V. "
    "Xfce, Cinnamon, MATE, LXQt, Budgie, Flatpak, Flathub and Calamares are names of their projects. "
    "PayPal is a trademark of PayPal, Inc. Facebook is a trademark of Meta Platforms, Inc. All other names "
    "belong to their owners and are used only to say what works with what.<br><br>"
    "<b>{0} is not affiliated with, sponsored or endorsed by Debian or by any of these projects.</b> "
    "Give your distribution a name and logo of your own: a distribution called 'Debian ...' or using the "
    "Debian logo must follow the Debian trademark policy (debian.org/trademark).").format(APP_NAME)


def real_user():
    """The person who started the program (pkexec or sudo), or None."""
    uid = os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID")
    if uid and uid.isdigit():
        try:
            return pwd.getpwuid(int(uid)).pw_name
        except KeyError:
            return None
    return None


def open_url(url):
    """Open a web page or file in the user's browser, not as root."""
    user = real_user()
    if os.geteuid() == 0 and user and shutil.which("runuser") and shutil.which("xdg-open"):
        env = {k: v for k, v in os.environ.items() if k in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
                                                            "XAUTHORITY", "LANG", "DBUS_SESSION_BUS_ADDRESS")}
        uid = pwd.getpwnam(user).pw_uid
        env.setdefault("XDG_RUNTIME_DIR", "/run/user/{}".format(uid))
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/{}/bus".format(uid))
        env["HOME"] = pwd.getpwnam(user).pw_dir
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
        subprocess.Popen(["runuser", "-u", user, "--", "xdg-open", url], env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    from eduka_customizer.qt.core import QUrl
    from eduka_customizer.qt.gui import QDesktopServices
    return QDesktopServices.openUrl(QUrl(url if "://" in url else "file://" + url))


def guide_path(lang="id"):
    """The PDF user guide (installed, or in the source tree)."""
    name = "DistroForge-Panduan.pdf" if lang == "id" else "DistroForge-Guide.pdf"
    for base in (Path("/usr/share/doc/distroforge"), Path(__file__).resolve().parents[3] / "docs"):
        if (base / name).exists():
            return base / name
    return None


def gpl_text():
    for p in ("/usr/share/common-licenses/GPL-3", "/usr/share/licenses/common/GPL3/license.txt"):
        if Path(p).exists():
            return Path(p).read_text(errors="replace")
    return ("GNU GENERAL PUBLIC LICENSE, Version 3, 29 June 2007\n\n"
            "This program is free software: you can redistribute it and/or modify it under the terms of the GNU "
            "General Public License as published by the Free Software Foundation, either version 3 of the License, "
            "or (at your option) any later version.\n\nThis program is distributed in the hope that it will be "
            "useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR "
            "A PARTICULAR PURPOSE. See the GNU General Public License for more details: "
            "https://www.gnu.org/licenses/gpl-3.0.html")


class AboutPage(Page):
    title = "About"
    nav_title = "About"
    subtitle = "{} {} — build your own Debian-based Linux distribution as a live ISO.".format(APP_NAME, VERSION_LABEL)
    icon_names = ("help-about", "dialog-information")
    needs_rootfs = False

    def build(self):
        c = self.card(APP_NAME)
        logo = QLabel()
        from eduka_customizer.gui.main_window import app_icon
        logo.setPixmap(app_icon().pixmap(96, 96))
        info = label("<span style='font-size:16pt; font-weight:800'>{}</span> {}<br>"
                     "Free and open source software, licensed under the GNU General Public License "
                     "version 3 or later ({}).<br>"
                     "Made by {} and contributors. {} was called {} before version 0.17.<br>"
                     "Project page: {}".format(APP_NAME, VERSION_LABEL, LICENSE, AUTHOR, APP_NAME, OLD_NAME,
                                               HOMEPAGE))
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        c.add(hbox(logo, info, None))
        c.add(hbox(button("♥  Donate with PayPal", lambda: open_url(DONATE_URL), "primary",
                          tooltip=DONATE_URL),
                   button("Follow on Facebook", lambda: open_url(FACEBOOK_URL), tooltip=FACEBOOK_URL),
                   button("Project page", lambda: open_url(HOMEPAGE), tooltip=HOMEPAGE), None,
                   button("User guide (PDF, Indonesia)", lambda: self.open_guide("id")),
                   button("User guide (PDF, English)", lambda: self.open_guide("en"))))
        c.add(label("{} is free. If it helps you, a donation keeps the work going: {}".format(APP_NAME, DONATE_URL),
                    "muted"))

        c = self.card("License", "You may use, study, share and change {} under the terms of the GNU GPL "
                                 "version 3 or later. It comes with ABSOLUTELY NO WARRANTY.".format(APP_NAME))
        c.add(hbox(button("Show the license (GPL-3.0)", self.show_license), None))

        c = self.card("Credits")
        c.add(label("{0} by {1}.<br>{0} is a rewrite of <i>Customizer</i> by Ivailo Monev, Mubiin Kimura, Graham "
                    "Cantin and contributors (GPL-2.0-or-later). Ideas are taken from <i>Cubic</i> (GPL-3.0), "
                    "<i>remastersys</i> (GPL-3.0) and <i>penguins-eggs</i> (MIT); no code of these projects is "
                    "copied. Menu icons from the <i>Papirus</i> icon theme (GPL-3.0).".format(APP_NAME, AUTHOR)))

        c = self.card("Components and their licenses",
                      "{} uses these free software projects (installed from your distribution, not copied into "
                      "{}). The ISO you build contains the packages of the Debian archive, each under its own "
                      "license: see /usr/share/doc/<package>/copyright inside the image.".format(APP_NAME, APP_NAME))
        t = table(["Component", "Used for", "License", "Home page"])
        t.setMinimumHeight(330)
        fill(t, COMPONENTS)
        t.setSortingEnabled(False)
        for i in range(3):
            t.resizeColumnToContents(i)
        c.add(t)

        c = self.card("Trademarks")
        c.add(label(TRADEMARKS))

    def open_guide(self, lang):
        p = guide_path(lang)
        if not p:
            self.main.stage_label.setText("The user guide is not installed")
            return
        open_url(str(p))

    def show_license(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("GNU General Public License version 3")
        dlg.resize(760, 640)
        lay = QVBoxLayout(dlg)
        text = QPlainTextEdit(gpl_text())
        text.setReadOnly(True)
        lay.addWidget(text)
        lay.addWidget(hbox(None, button("Close", dlg.accept, "primary")))
        dlg.exec()
