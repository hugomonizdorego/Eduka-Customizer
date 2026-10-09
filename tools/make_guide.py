#!/usr/bin/env python3
"""Write the PDF user guide docs/DistroForge-Guide.pdf from the text below and
docs/screenshots.

    QT_QPA_PLATFORM=offscreen python3 tools/make_guide.py
"""

import html
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eduka_customizer import APP_NAME, AUTHOR, DONATE_URL, FACEBOOK_URL, HOMEPAGE, VERSION_LABEL  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"

# Each chapter: (title, [paragraph or ("img", file, caption) or ("list", [items]) or ("code", text)]).
# Text may hold <b>, <i> and <code>; everything else is escaped.

EN = {
    "file": "DistroForge-Guide.pdf",
    "title": "User Guide",
    "lead": "Build your own Debian-based Linux distribution as a live ISO, step by step.",
    "toc": "Contents",
    "chapters": [
        ("What is {app}?", [
            "{app} is free and open source software (GPL-3.0-or-later) to build your own Linux distribution from "
            "Debian or a Debian derivative. The result is a live ISO that boots from a USB stick or DVD (BIOS and "
            "UEFI) and installs with the Calamares installer.",
            "You can start from:",
            ("list", ["a live ISO of Debian or a Debian derivative (for example LMDE, MX Linux, antiX, Kali Linux, "
                      "Parrot OS, Deepin, SparkyLinux, BunsenLabs, Q4OS)",
                      "a new Debian base system (stable, testing or sid) made with mmdebstrap/debootstrap",
                      "a copy of this computer (snapshot)"]),
            "Ubuntu-based ISOs (Ubuntu, Linux Mint's Ubuntu edition, Pop!_OS, elementary OS, Zorin OS) are not "
            "supported: {app} is made for Debian-based distributions. {app} itself installs on Debian, Debian "
            "derivatives and Ubuntu.",
            "The work is split into 13 steps. The next step opens when the one before is done, so you always know "
            "what comes next. Experts can open every step in Settings.",
            ("list", ["1 Start · 2 Repositories · 3 Identity & Branding · 4 Users · 5 Language · 6 Desktop",
                      "7 Software · 8 Kernel & Boot · 9 Look & Feel · 10 Installer · 11 Advanced",
                      "12 Review & Apply · 13 Check & Build"]),
        ]),
        ("Installing and starting", [
            "Install the .deb package (it pulls in every tool it needs):",
            ("code", "sudo apt install ./distroforge_0.9.0~beta_all.deb"),
            "Start it from the application menu (<b>DistroForge</b>) or a terminal:",
            ("code", "distroforge            # the window (asks for the admin password)\n"
                     "sudo distroforge --help  # command line"),
            "The old command <code>eduka-customizer</code> still works and opens {app}. Old settings in "
            "/etc/eduka-customizer are read automatically.",
            "Needs: Debian 12 or newer (or a derivative), 4 GB RAM, free disk space of three times the ISO size.",
        ]),
        ("Step 1 · Start: create a project", [
            "Choose where your distribution comes from: open an ISO, download an official Debian live ISO, "
            "bootstrap a new Debian base, or copy this computer. Each project is one folder with the system, the "
            "settings and the built ISO, each in its own sub-folder (see 'The project folder').",
            "<b>Purpose</b> asks what the distribution is for (home, office, school, gaming, server, ...) and the "
            "ISO edition (minimal, standard, full). Use or ignore its recommendations.",
            ("img", "01-start-step-by-step.png", "Step 1: create or open a project"),
            "The <b>Quick Wizard</b> asks everything important on 8 pages and prepares it all at once.",
            ("img", "00-wizard-step1.png", "Quick Wizard"),
        ]),
        ("Steps 2 to 5 · Repositories, Identity, Users, Language", [
            "<b>Repositories</b>: the Debian version (stable, testing, sid), the mirror, contrib/non-free-firmware "
            "and other repositories.",
            "<b>Identity & Branding</b>: name, version, code name, web site, logo and wallpaper. The values start "
            "from what the ISO has. {app} builds a branding package that replaces os-release, lsb-release, issue, "
            "logos, the GRUB menu and the installer branding. Use a name and logo of your own: names such as "
            "'Debian ...' or 'Ubuntu ...' are trademarks, and the check warns about them.",
            ("img", "03b-identity-branding.png", "Identity & Branding"),
            "<b>Users</b>: the live user (default <code>live</code>, full name <code>Live</code>), with or without "
            "a password, automatic login and more accounts. <b>Language</b>: default language, keyboard, time zone "
            "(default Asia/Dili) and language packs, also for the installer and the boot menu.",
        ]),
        ("Steps 6 and 7 · Desktop and Software", [
            "Choose a desktop (GNOME, KDE Plasma, Xfce, Cinnamon, MATE, LXQt, Budgie, ...) or a window manager and "
            "its edition under the names the desktop itself uses. Set the login screen and default session too.",
            ("img", "06-desktop-editions.png", "Desktops and editions"),
            "<b>Software</b>: search, install and remove Debian packages; add Flathub applications by category; and "
            "replace the default applications (browser, mail, editor, terminal, ...) for all users.",
            ("img", "07-software-packages.png", "Packages"),
        ]),
        ("Step 8 · Kernel & Boot", [
            "Three tabs: <b>Kernel</b> (Debian, backports or third-party kernels, firmware, drivers), <b>Boot "
            "Loader</b> (what installed computers start with) and <b>Boot Menu</b> (the menu of the ISO itself).",
            "<b>Boot Loader.</b> Install the boot loaders you want into the image, remove the others, choose the "
            "one the installer puts on computers (<b>Use for installed systems</b>) and set it up below:",
            ("list", ["<b>GRUB 2</b> — BIOS and UEFI, menus, themes, other operating systems. Recommended. Settings: "
                      "timeout, kernel options, menu style, default entry, os-prober, recovery entries, resolution.",
                      "<b>GRUB 2 with Secure Boot</b> — the same, signed by Debian and started by shim.",
                      "<b>systemd-boot</b> — small and fast, UEFI. Settings: timeout, kernel options, default entry, "
                      "editor, screen mode.",
                      "<b>rEFInd</b> — graphical, finds every system by itself, UEFI (Calamares 3.3). Settings: "
                      "timeout, kernel options, resolution, text mode, tools row.",
                      "<b>EFISTUB</b> — no boot loader: the UEFI firmware starts the kernel directly. Secure Boot "
                      "must be off. Settings: kernel options, name in the firmware menu.",
                      "<b>Syslinux / EXTLINUX</b> — the small classic boot loader for BIOS computers (/boot on "
                      "ext2/3/4, not encrypted). Settings: timeout, kernel options, menu title, graphical menu."]),
            "Every choice works with the Calamares installer. GRUB, systemd-boot and rEFInd are installed by "
            "Calamares itself; EFISTUB and Syslinux by an own installer step. When a boot loader cannot work on a "
            "computer (Syslinux on UEFI, EFISTUB on BIOS, an encrypted /boot) the next one that works is used, "
            "GRUB last, so the installation does not stop with an error. After kernel updates EFISTUB and Syslinux "
            "are kept up to date by themselves.",
            ("img", "08b-boot-loader.png", "Boot Loader"),
            ("img", "08b2-boot-loader-settings.png", "The settings of the selected boot loader"),
            "<b>Boot Menu</b>: title, timeout, kernel options and background of the ISO's menu, a third-party "
            "GRUB theme (checked first, refused when GRUB could not show it), the menu designer (rename, reorder, "
            "add or remove entries) and, for experts, the boot files themselves.",
            ("img", "08d-boot-menu-grub-design.png", "GRUB theme and menu designer"),
        ]),
        ("Step 9 · Look & Feel", [
            "Five tabs: <b>Themes & Icons</b> (only what fits the chosen desktop), <b>Wallpaper & Login</b>, "
            "<b>Plymouth</b> (boot animation), <b>System Sounds</b> (start-up, login, log out, errors, "
            "notifications) and <b>Welcome Screen</b> (four pages shown after the first login).",
            ("img", "09-look-themes-icons.png", "Themes and icons"),
            ("img", "09e-look-welcome-screen.png", "Welcome screen"),
        ]),
        ("Steps 10 and 11 · Installer and Advanced", [
            "<b>Installer</b>: the Calamares installer — modules, order, slides, default partitioning and texts. "
            "<b>Check the installer</b> finds mistakes before the build; the <b>How to fix</b> column says whether "
            "a problem is fixed automatically.",
            ("img", "10b-installer-check.png", "Installer check"),
            "<b>Advanced</b>: a terminal inside the image, the live session in a window (Xephyr), hook scripts, "
            "JSON recipes and the package workshop to change files of installed Debian packages.",
        ]),
        ("Step 12 · Review & Apply", [
            "Changes from steps 2 to 11 <b>do not</b> change the image right away. They all wait in the Review & "
            "Apply list. The blue button at the top shows how many are waiting.",
            ("list", ["Tick every change you are sure about.",
                      "<b>Go back and change it</b> opens the step of that change.",
                      "<b>Remove from the list</b> drops a change; <b>Up/Down</b> change the order.",
                      "<b>Apply all changes</b> is enabled when everything is ticked. If one change fails, the ones "
                      "applied before it leave the list and the rest keep waiting."]),
            "Experts can apply every change at once (Settings → Apply every change at once).",
            ("img", "12-review-apply.png", "Review & Apply"),
        ]),
        ("Step 13 · Check & Build", [
            "<b>Check now</b> finds what would make the build fail, the ISO not boot, or private data leak into "
            "it. Every row says how to fix it:",
            ("list", ["<b>Automatic: ...</b> — press <b>Fix automatically</b>; {app} fixes it and checks again.",
                      "<b>By hand (double-click)</b> — double-click the row to open the right step."]),
            "When you press <b>Build ISO image</b> with problems left, {app} asks: <b>Fix automatically</b>, <b>I "
            "will fix it myself</b> or <b>Build anyway</b>.",
            ("img", "13-check-build.png", "Check & Build"),
        ]),
        ("ISO size", [
            "Choose a target size: as small as possible, 100 MB, 300 MB, 500 MB, 700 MB (CD), 1 GB, 2 GB, 4.4 GB "
            "(DVD) or no limit. <b>Estimate</b> compresses a sample of the system and computes the size of every "
            "method.",
            "Squashfs compression is <b>lossless</b>: every file comes back exactly as it was. A smaller ISO is "
            "never a damaged ISO, it only takes longer to build (xz is smallest and slowest, lz4 fastest).",
            "When the target is too small, {app} suggests safe size savers: documentation, manual pages, unused "
            "translations, APT lists and old kernels. License files always stay. Removing applications you do "
            "not need helps most.",
            ("img", "13b-build-options.png", "Target size and build options"),
        ]),
        ("The project folder and keeping only the ISO", [
            "Everything of a project is in one folder, each part in its own sub-folder, so you can also open them "
            "and change files by hand: <code>rootfs/</code> (the system), <code>iso/</code> (boot menus and the "
            "files around the system), <code>hooks/</code> (your scripts), <code>workshop/</code>, "
            "<code>branding/</code>, and <code>boot/</code>, <code>cache/</code>, <code>logs/</code>, "
            "<code>output/</code> made by {app}. README.txt in the folder explains them.",
            ("img", "13c-result-project-folder.png", "Result and project folder"),
            "The build folders are big. When the ISO is finished and tested, <b>Keep only the ISO...</b> (or "
            "closing the window after a build) deletes everything of the project but the ISO and its checksum "
            "files, which move into the project folder. Nothing is deleted while anything is still mounted inside "
            "the project, and files of your own in the folder stay. The command line does the same with "
            "<code>distroforge clean --keep-iso</code>.",
        ]),
        ("Testing and writing to USB", [
            "After the build, <b>Boot ISO</b> in the <b>Test in a virtual machine</b> card boots the ISO with QEMU "
            "(BIOS, UEFI or UEFI with Secure Boot). The ISO is hybrid: write it to a USB stick with GNOME Disks, "
            "balenaEtcher, Ventoy or:",
            ("code", "sudo dd if=mylinux.iso of=/dev/sdX bs=4M status=progress oflag=sync"),
            "Replace /dev/sdX with the right USB device; everything on it is erased.",
        ]),
        ("Command line", [
            "Every step is also available in a terminal, in the order of the work. The commands apply each change "
            "at once (Review & Apply is only in the window).",
            ("code", "sudo distroforge new --iso debian-live.iso ~/mylinux\n"
                     "cd ~/mylinux\n"
                     "sudo distroforge brand identity name=\"My Linux\" version=1.0\n"
                     "sudo distroforge apt install vlc gimp\n"
                     "sudo distroforge boot-loader list\n"
                     "sudo distroforge boot-loader set systemd-boot TIMEOUT=3\n"
                     "sudo distroforge boot-loader use systemd-boot\n"
                     "sudo distroforge check --fix\n"
                     "sudo distroforge build --target-size 700\n"
                     "sudo distroforge test\n"
                     "sudo distroforge clean --keep-iso"),
            "<code>distroforge --help</code> lists the commands by step; <code>distroforge COMMAND --help</code> "
            "explains one command.",
        ]),
        ("Common problems and feedback", [
            ("list", ["<b>'grub needs /usr/sbin/grub-install in the image'</b> — not reported for live ISOs that "
                      "install GRUB from the ISO pool during installation. If it shows, press Fix automatically.",
                      "<b>Half-installed packages</b> — Fix automatically runs dpkg --configure -a and "
                      "apt-get -f install.",
                      "<b>Not enough disk space</b> — remove caches with <code>sudo distroforge clean</code>, or "
                      "keep only the ISO of finished projects.",
                      "<b>No internet</b> — installing packages and Flatpaks needs internet; all other edits work "
                      "offline.",
                      "<b>Log</b> — every message is in the log panel and in /tmp/distroforge/distroforge.log."]),
            "<b>Send feedback</b> (in the sidebar, in Settings, and in every error message) sends a bug report, an "
            "error, an idea or a question to the developers, with screenshots or other files and, if you agree, "
            "the logs. Without internet the report is kept and sent the next time {app} starts.",
            ("img", "15-send-feedback.png", "Send feedback"),
        ]),
        ("License, trademarks and support", [
            "{app} is free software under the GNU General Public License version 3 or later, WITHOUT ANY WARRANTY. "
            "The license of every component (Python, Qt, squashfs-tools, xorriso, GRUB, systemd-boot, rEFInd, "
            "Syslinux, Calamares, live-boot, Papirus, ...) is listed on the <b>About</b> tab of Settings & About. "
            "The packages in your ISO each keep their own license (/usr/share/doc/PACKAGE/copyright).",
            "Debian is a registered trademark of Software in the Public Interest, Inc.; Linux® is the registered "
            "trademark of Linus Torvalds. {app} is not affiliated with, sponsored or endorsed by Debian. Give your "
            "distribution a name and logo of its own.",
            ("img", "14b-about.png", "About"),
            "Made by {author}. If {app} helps you, a donation keeps the project going:",
            ("list", ["PayPal: {donate}", "Facebook: {facebook}", "Project: {home}"]),
        ]),
    ],
}


def fmt(text):
    """Escape everything but the few tags the texts use, then fill in the names."""
    safe = html.escape(text, quote=False)
    for tag in ("b", "i", "code"):
        safe = safe.replace("&lt;{}&gt;".format(tag), "<{}>".format(tag)).replace(
            "&lt;/{}&gt;".format(tag), "</{}>".format(tag))
    return safe.format(app=APP_NAME, author=AUTHOR, donate=DONATE_URL, facebook=FACEBOOK_URL, home=HOMEPAGE)


def img(path, width):
    """<img> with both sizes, so the layout reserves exactly the scaled picture."""
    from eduka_customizer.qt.gui import QImage
    q = QImage(str(path))
    if q.isNull():
        raise SystemExit("missing picture: {}".format(path))
    width = min(width, q.width())
    return "<img src='{}' width='{}' height='{}'>".format(path, width, int(q.height() * width / q.width()))


def to_html(guide, width):
    parts = ["<div align='center' style='line-height: 100%'>",
             "<br>{}<br>".format(img(ROOT / "icons/hicolor/256x256/apps/distroforge.png", 140)),
             "<h1 style='font-size: 34pt'>{}</h1>".format(APP_NAME),
             "<p style='font-size: 18pt'>{} · {}</p>".format(guide["title"], VERSION_LABEL),
             "<p style='font-size: 12pt'>{}</p><br>".format(fmt(guide["lead"])),
             "{}<br><br>".format(img(SHOTS / "08b-boot-loader.png", width)),
             "<p>{} · GPL-3.0-or-later · {}</p>".format(AUTHOR, HOMEPAGE), "</div>",
             "<h2 style='page-break-before: always'>{}</h2><ol>".format(guide["toc"])]
    if guide.get("note"):
        parts.insert(-1, "<p><i>{}</i></p>".format(fmt(guide["note"])))
    parts += ["<li>{}</li>".format(fmt(t)) for t, _b in guide["chapters"]]
    parts.append("</ol>")
    for n, (title, body) in enumerate(guide["chapters"], 1):
        parts.append("<h2 style='page-break-before: always'>{}. {}</h2>".format(n, fmt(title)))
        for b in body:
            if isinstance(b, str):
                parts.append("<p>{}</p>".format(fmt(b)))
            elif b[0] == "list":
                parts.append("<ul>" + "".join("<li>{}</li>".format(fmt(x)) for x in b[1]) + "</ul>")
            elif b[0] == "code":
                parts.append("<pre style='background-color:#eef3f1'>{}</pre>".format(html.escape(b[1])))
            elif b[0] == "img":
                parts.append("<p align='center' style='line-height: 100%'>{}<br><i>{}</i></p>".format(img(SHOTS / b[1], width), fmt(b[2])))
    return "\n".join(parts)


def write(guide, out):
    from eduka_customizer.qt.core import QMarginsF, QSizeF
    from eduka_customizer.qt.gui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    pdf = QPdfWriter(str(out))
    pdf.setResolution(96)
    pdf.setTitle("{} {}".format(APP_NAME, guide["title"]))
    pdf.setCreator("{} {}".format(APP_NAME, VERSION_LABEL))
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                  QMarginsF(18, 16, 18, 16), QPageLayout.Unit.Millimeter))
    rect = pdf.pageLayout().paintRectPixels(96)
    doc = QTextDocument()
    doc.setDefaultFont(QFont("DejaVu Sans", 10))
    doc.setDefaultStyleSheet("h1, h2 { color: #0f6e56; } h2 { font-size: 17pt; } pre { font-size: 9pt; } "
                             "p, li { line-height: 130%; }")
    doc.setHtml(to_html(guide, rect.width() - 8))
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    doc.print(pdf) if hasattr(doc, "print") else doc.print_(pdf)
    print("wrote", out)


def main():
    from eduka_customizer.qt.gui import QGuiApplication
    app = QGuiApplication(sys.argv)  # noqa: F841 (fonts and images need it)
    write(EN, ROOT / "docs" / EN["file"])


if __name__ == "__main__":
    main()
