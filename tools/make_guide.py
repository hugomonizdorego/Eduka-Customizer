#!/usr/bin/env python3
"""Write the PDF user guide docs/Disco-Guide.pdf from the text below and
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

from disco import APP_NAME, AUTHOR, DONATE_URL, FACEBOOK_URL, HOMEPAGE, VERSION_LABEL  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"

# Each chapter: (title, [paragraph or ("img", file, caption) or ("list", [items]) or ("code", text)]).
# Text may hold <b>, <i> and <code>; everything else is escaped.

EN = {
    "file": "Disco-Guide.pdf",
    "title": "Step-by-step Guide",
    "lead": "Customize a Debian live ISO into your own distribution: open the ISO, change what you like, press Finish.",
    "toc": "Contents",
    "cover": "01-welcome.png",
    "chapters": [
        ("What is {app}?", [
            "<b>{app} (Distro Custom)</b> is free and open source software (GPL-3.0-or-later) that makes your own "
            "Linux distribution from a <b>Debian</b> or <b>Devuan</b> live ISO. It is made to be easy: you go "
            "through the steps with <b>Next</b>, change only what you want, and press <b>Finish</b>. The result "
            "is a live ISO (BIOS and UEFI) with the Calamares installer, or an SD-card image for the Raspberry Pi.",
            "{app} uses Debian's own tools only: <code>live-boot</code>, <code>mksquashfs</code>, "
            "<code>xorriso</code>, <code>mmdebstrap</code>/<code>debootstrap</code>, <code>chroot</code> and "
            "Calamares. Nothing of Ubuntu is used (no casper, no PPAs).",
            ("table", ["Step", "What you do there"], [
                ["Welcome", "What {app} does, recommendations, support."],
                ["1 Start", "Extract an ISO into a new project, or continue a project."],
                ["2 System", "Repositories, name of the system, system files, users, language."],
                ["3 Software", "Desktop, applications by category, Flatpak, default applications."],
                ["4 Startup", "What starts by itself: services and programs after login."],
                ["5 Branding", "Wallpaper and logo, login screen, boot splash, a PDF on every desktop."],
                ["6 Look & Feel", "Themes, sounds, welcome screen, terminal prompt and browser."],
                ["7 Boot", "Kernel, boot loader, boot menu, init system, Raspberry Pi."],
                ["8 Installer", "Calamares, no installer, or your own packages."],
                ["9 Files & Terminal", "Your folders (no root needed), the system as administrator, a terminal."],
                ["10 Review & Apply", "The list of your changes, applied all at once."],
                ["11 Build", "Finish: checks, then the ISO or SD-card image."]]),
        ]),
        ("Before you start", [
            ("steps", ["Install {app} (it brings every tool it needs):",
                       "Connect to the internet. Extracting and editing work offline, but installing packages, "
                       "desktops, Flatpak applications and kernels needs internet.",
                       "Download an ISO to start from. Recommended: the small <b>Debian live standard ISO</b> (no "
                       "desktop), then add the desktop you want in step 3.",
                       "Start <b>D!sco</b> from the menu. It asks for the administrator password: it needs it to "
                       "build systems."]),
            ("code", "sudo apt install ./disco_0.11.1_all.deb"),
            ("table", ["Recommended", "Why"], [
                ["Internet connection", "packages, desktops, Flatpaks, kernels, updates"],
                ["Debian 12 or newer (or a Debian-based system)", "the computer that runs {app}"],
                ["4 GB of memory, about 20 GB free disk space", "the system, the ISO and the compressed copy"],
                ["The Debian live standard ISO", "a small, clean start"]]),
            "The <b>Welcome</b> page opens first. Untick <b>Show this page when D!sco starts</b> to go straight "
            "to Start next time. <b>Donate with PayPal</b> supports the project.",
            ("img", "01-welcome.png", "The Welcome page"),
        ]),
        ("Step 1 · Start", [
            "<b>Customize an ISO</b> (left):",
            ("steps", ["Press <b>Browse...</b> next to <b>ISO file</b> and choose the ISO.",
                       "Type a <b>Name</b> for your distribution; the <b>Folder</b> of the project follows it.",
                       "Optionally choose the <b>Language</b> of the system.",
                       "Press <b>Extract and start</b>. When it is done, {app} opens step 2."]),
            "<b>Continue a project</b> (right): choose a project from the list and press <b>Continue</b>. {app} "
            "opens the step where you stopped. Projects are kept: close {app} at any time.",
            "The line at the top shows whether the internet connection works.",
            ("img", "02b-start-continue.png", "Start: customize an ISO or continue a project"),
            "<b>Other ways to start</b>: download an official Debian ISO (checked with Debian's SHA256SUMS), make a "
            "<b>new system without an ISO</b> for a PC, an ARM64 machine, a Raspberry Pi or RISC-V, or copy this "
            "computer.",
        ]),
        ("Moving through the steps", [
            "Every step has a bar at the bottom: <b>Back</b> goes to the step before, <b>Next</b> marks the step "
            "done and opens the next one. Skip what you do not want to change: just press Next. The last step "
            "has <b>Finish</b>, which builds the image.",
            "Most changes do not change the system at once: they wait in <b>Review & Apply</b> (step 10), so you "
            "can check them first. The blue button at the top shows how many wait.",
            "A step opens after the one before it is done. Experts can open every step at any time: <b>Settings → "
            "Free navigation</b>.",
        ]),
        ("Step 2 · System", [
            "Tabs: <b>Repositories</b> (Debian or Devuan release, mirror, extra repositories with their keys), "
            "<b>Identity</b> (name, version, website, computer name), <b>System files</b>, <b>Users</b> (the live "
            "user, passwords, more accounts) and <b>Language</b> (language, keyboard, time zone).",
            "<b>System files</b> edits the files that tell who the system is. <b>Template from Identity</b> fills a "
            "file for you; change it, then <b>Save to the system</b>.",
            ("table", ["File", "Example"], [
                ["/etc/os-release", 'NAME="My Linux" · VERSION="1.0" · ID=mylinux · PRETTY_NAME · HOME_URL · LOGO'],
                ["/etc/lsb-release", 'DISTRIB_ID="My Linux" · DISTRIB_RELEASE=1.0 · DISTRIB_DESCRIPTION'],
                ["/etc/issue", "Welcome to My Linux 1.0 - \\n \\l"],
                ["/etc/issue.net", "Welcome to My Linux 1.0"],
                ["/etc/hostname, /etc/hosts", "mylinux · 127.0.1.1 mylinux"],
                ["/etc/motd", "the message after logging in"]]),
            ("img", "03c-system-files.png", "System files"),
        ]),
        ("Step 3 · Software", [
            "<b>Desktop</b>: choose a desktop (Xfce, GNOME, KDE Plasma, Cinnamon, MATE, LXQt...) or a window "
            "manager and how complete it is. The login screen and session follow it.",
            "<b>Packages</b>: <b>Popular applications</b> lists programs by category with tick boxes: tick them and "
            "press <b>Install ticked</b>. Below it, every Debian package can be searched, added or removed, and "
            "the applications of the ISO can be removed.",
            ("img", "04b-applications.png", "Popular applications"),
            "<b>Flatpak</b>: applications from Flathub, in the ISO or installed at the first start. <b>Default "
            "apps</b>: another browser, mail program, editor or terminal for everyone.",
        ]),
        ("Step 4 · Startup", [
            "What starts by itself, switched on or off with a tick:",
            ("list", ["<b>Services</b> start with the system, before anyone logs in (network, printing, SSH, "
                      "Bluetooth, updates...). 🔒 marks services the system needs: they stay on.",
                      "<b>Programs after login</b> start on every user's desktop (/etc/xdg/autostart).",
                      "<b>Add a program</b>: a name and a command, for example a welcome page in the browser."]),
            "Change the ticks and press <b>Apply the ticks</b>. Turning off what you do not need makes the system "
            "start faster.",
            ("img", "05-startup.png", "Startup"),
        ]),
        ("Step 5 · Branding", [
            "<b>Wallpaper & Logo</b> is the easy way, the same for every picture:",
            ("steps", ["Press <b>Choose...</b> (or drop a picture on its box).",
                       "Keep <b>Set as default</b> ticked (untick it to only add the picture to the system).",
                       "Press <b>Apply</b>. Pictures: desktop wallpaper, logo, login screen, boot menu, picture of "
                       "new users. <b>Apply all chosen pictures</b> does them all."]),
            "The <b>logo</b> goes everywhere: menu and system icon, os-release LOGO, login screen, installer and a "
            "boot splash made from it.",
            ("img", "06-wallpaper-logo.png", "Wallpaper & Logo"),
            "The other tabs: <b>Wallpaper & Login</b> (a wallpaper gallery and login screen themes), <b>Boot "
            "Splash</b> (Plymouth themes), <b>Desktop document</b> (a PDF with any title about your system, put on "
            "every user's desktop) and <b>Distro Branding</b> (a package with your name and logo everywhere).",
            ("img", "06b-desktop-document.png", "Desktop document"),
        ]),
        ("Step 6 · Look & Feel", [
            "<b>Themes & Icons</b>, <b>System Sounds</b>, <b>Welcome Screen</b> (pages shown after the first login) "
            "and <b>Terminal & Browser</b>: the message after login, the bash prompt of every user, and the home "
            "page, bookmarks and privacy of Firefox ESR and Chromium.",
            ("img", "07b-terminal-browser.png", "Terminal & Browser"),
        ]),
        ("Step 7 · Boot", [
            "<b>Kernel</b> (Debian kernels, backports, third-party kernels, firmware), <b>Boot Loader</b> (what "
            "installed computers start with: GRUB, systemd-boot, rEFInd, EFISTUB, Syslinux), <b>Boot Menu</b> (the "
            "menu of the ISO), <b>Init System</b> (systemd, SysVinit, OpenRC, runit) and <b>Raspberry Pi</b> "
            "(config.txt, kernel options, image size).",
            ("img", "08b-boot-loader.png", "Boot loader"),
        ]),
        ("Step 8 · Installer", [
            "<b>Which installer</b>: Calamares (recommended), none (a live system only), or <b>your own .deb "
            "packages</b>: drop them on the page and press <b>Install them now</b>. Below it: the name, pictures, "
            "slides and rules of Calamares, and <b>Check the installer</b>.",
            ("img", "09-installer.png", "Installer"),
        ]),
        ("Step 9 · Files & Terminal", [
            "<b>Your folders</b> belong to you: open them in your own file manager and add, change or delete "
            "anything, <b>no administrator rights needed</b>.",
            ("table", ["Folder", "What it is for"], [
                ["overlay", "files for the system: overlay/etc/skel/.bashrc becomes /etc/skel/.bashrc"],
                ["hooks", "your scripts (*.sh), run inside the system"],
                ["branding", "your pictures and documents"],
                ["debs", "your own .deb packages"],
                ["iso", "the boot menus and splash pictures of the ISO"],
                ["output", "the finished ISO and SD-card images"]]),
            "<b>Copy my files into the system</b> copies overlay into the system with owner root; <b>Run my "
            "scripts</b> runs the scripts. <b>Give me full access</b> hands the folders to you again.",
            ("img", "10-files.png", "Your folders"),
            "<b>The system</b> is changed as administrator, here in {app}: choose a folder (/etc, /etc/skel, "
            "/usr/share...), select a file, change it and press <b>Save file</b>.",
            ("warn", "The system folder is not opened for everyone on purpose: its owners and permissions go into "
                     "the ISO as they are, and a system where everyone may change every file is unsafe and does "
                     "not start correctly (sudo and SSH refuse to work). Use the overlay folder instead."),
            "<b>Terminal & Live</b>: a terminal inside the system and the desktop of the system in a window. "
            "<b>Package Workshop</b>: change the files of an installed Debian package.",
        ]),
        ("Step 10 · Review & Apply", [
            "Every change of steps 2 to 9 waits here. Tick the ones you are sure about, <b>Try them first</b> in a "
            "preview if you like, then <b>Apply all changes</b>.",
            ("img", "11-review-apply.png", "Review & Apply"),
        ]),
        ("Step 11 · Build: Finish", [
            "Press <b>Finish: build the image</b> (or <b>Build ISO image</b>). {app} checks the system first and "
            "says how to fix each problem: <b>Fix automatically</b>, or double-click a row to open the right step.",
            "Choose a target size if you like (100 MB to 4.4 GB). Compression is lossless: a smaller ISO only takes "
            "longer to build. For a Raspberry Pi project the button builds the SD-card image.",
            ("img", "12-build.png", "Build"),
        ]),
        ("Testing and writing the image", [
            "<b>Boot ISO</b> starts the ISO in a virtual machine (QEMU). Then write it to a USB stick:",
            ("code", "lsblk                     # find the USB stick, for example /dev/sdb\n"
                     "sudo dd if=mylinux-1.0-stable-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync"),
            ("warn", "dd erases everything on the device named in of= without asking. A wrong letter erases "
                     "your own disk: check it with lsblk first. GNOME Disks (Restore Disk Image) is safer."),
            "An SD-card image for the Raspberry Pi:",
            ("code", "xzcat mypi-1.0-stable-arm64.img.xz | \\\n"
                     "    sudo dd of=/dev/sdX bs=4M status=progress conv=fsync"),
        ]),
        ("Raspberry Pi, ARM64 and RISC-V", [
            "Start with <b>Other ways to start → New system (no ISO)</b> and choose the platform:",
            ("table", ["Platform", "Processor", "Result"], [
                ["PC, 64-bit / 32-bit (Debian 12)", "amd64 / i386", "ISO, BIOS + UEFI"],
                ["ARM 64-bit with UEFI", "arm64", "ISO, UEFI"],
                ["Raspberry Pi 3, 4, 400 (and 5, experimental)", "arm64", "SD-card image"],
                ["Raspberry Pi 2, 3 (32-bit)", "armhf", "SD-card image"],
                ["Raspberry Pi 1, Zero", "armel", "SD-card image"],
                ["RISC-V 64 with UEFI (experimental)", "riscv64", "ISO, UEFI"]]),
            "Other processors run through qemu-user on your PC:",
            ("code", "sudo apt install qemu-user-static binfmt-support"),
            "SD-card images are laid out like Debian's own (RASPIFIRM boot partition, RASPIROOT system partition "
            "that grows to the whole card). Before the first start, <code>sysconf.txt</code> on the boot "
            "partition can set the computer name and an SSH key:",
            ("code", "hostname=mypi\nroot_authorized_key=ssh-ed25519 AAAA... you@laptop"),
            ("img", "08c-raspberry-pi.png", "Raspberry Pi"),
        ]),
        ("Command line", [
            "Everything also works in a terminal (the commands apply each change at once):",
            ("code", "sudo disco new --iso debian-live-13.1.0-amd64-standard.iso /home/disco/mylinux\n"
                     "cd /home/disco/mylinux\n"
                     "sudo disco brand identity name=\"My Linux\" version=1.0\n"
                     "sudo disco apt install vlc gimp\n"
                     "sudo disco check --fix\n"
                     "sudo disco build --target-size 700\n"
                     "sudo disco test\n"
                     "disco platforms        # what D!sco builds for\n"
                     "disco --help           # every command"),
            "For automated builds: presets, package lists and <code>disco build-all</code>, or Debian's live-build "
            "with <code>disco live-build export</code>.",
        ]),
        ("Troubleshooting", [
            ("table", ["Problem", "What to do"], [
                ["No internet connection", "Connect, then press Check again on Start. Editing works offline."],
                ["NO_PUBKEY / signature errors from APT", "Add the key of the repository (Repositories → Add) or "
                 "install the keyring package (debian-archive-keyring, devuan-keyring)."],
                ["Kernel panic or 'Unable to find a medium' at live boot", "live-boot or the initramfs is missing: "
                 "Build → Fix automatically."],
                ["Exec format error (ARM or RISC-V system)", "sudo apt install qemu-user-static binfmt-support"],
                ["The system is still in use", "Close the terminal or live session of the system, or Unmount "
                 "everything (Files & Terminal → Terminal & Live)."],
                ["A button did nothing", "Look at the log at the bottom (Show log) or /tmp/disco/disco.log, and "
                 "use Send feedback."]]),
        ]),
        ("Cleaning up", [
            "The build folders are big. After a build, closing the window (or <b>Keep only the ISO</b> on Build, or "
            "<code>sudo disco clean --keep-iso</code>) deletes everything of the project but the images. Nothing is "
            "deleted while anything is mounted inside the project.",
            ("warn", "Never delete a project folder with rm -rf while a terminal or live session of it is open: "
                     "/dev and /proc of your computer are mounted inside it."),
        ]),
        ("License, trademarks and support", [
            "{app} is free software under the GNU General Public License version 3 or later, WITHOUT ANY WARRANTY. "
            "The licenses of its components are on the About tab of Settings & About.",
            "Debian is a registered trademark of Software in the Public Interest, Inc.; Raspberry Pi is a trademark "
            "of Raspberry Pi Ltd; Linux® is the registered trademark of Linus Torvalds. {app} is not affiliated "
            "with them. Give your distribution a name and logo of its own. The penguin of the {app} logo is a "
            "friend of Tux, the Linux mascot.",
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
    from disco.qt.gui import QImage
    q = QImage(str(path))
    if q.isNull():
        raise SystemExit("missing picture: {}".format(path))
    width = min(width, q.width())
    return "<img src='{}' width='{}' height='{}'>".format(path, width, int(q.height() * width / q.width()))


def to_html(guide, width):
    parts = ["<div align='center' style='line-height: 100%'>",
             "<br>{}<br>".format(img(ROOT / "icons/hicolor/256x256/apps/disco.png", 140)),
             "<h1 style='font-size: 34pt'>{}</h1>".format(APP_NAME),
             "<p style='font-size: 18pt'>{} · {}</p>".format(guide["title"], VERSION_LABEL),
             "<p style='font-size: 12pt'>{}</p><br>".format(fmt(guide["lead"])),
             "{}<br><br>".format(img(SHOTS / guide.get("cover", "01-builder.png"), width)),
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
            elif b[0] == "steps":
                parts.append("<ol>" + "".join("<li>{}</li>".format(fmt(x)) for x in b[1]) + "</ol>")
            elif b[0] == "code":
                parts.append("<pre style='background-color:#eef1f7'>{}</pre>".format(html.escape(b[1])))
            elif b[0] == "warn":
                parts.append("<table width='100%' cellpadding='8' style='background-color:#fdecea'><tr><td>"
                             "<b><font color='#b71c1c'>WARNING: {}</font></b></td></tr></table>".format(fmt(b[1])))
            elif b[0] == "table":
                head = "".join("<th align='left' style='background-color:#e3e8f4'>{}</th>".format(fmt(h))
                               for h in b[1])
                rows = "".join("<tr>" + "".join("<td>{}</td>".format(fmt(c)) for c in row) + "</tr>"
                               for row in b[2])
                parts.append("<table width='100%' border='1' cellspacing='0' cellpadding='4' "
                             "style='border-color:#c5cbe0'><tr>{}</tr>{}</table>".format(head, rows))
            elif b[0] == "img":
                parts.append("<p align='center' style='line-height: 100%'>{}<br><i>{}</i></p>".format(img(SHOTS / b[1], width), fmt(b[2])))
    return "\n".join(parts)


def write(guide, out):
    from disco.qt.core import QMarginsF, QSizeF
    from disco.qt.gui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    pdf = QPdfWriter(str(out))
    pdf.setResolution(96)
    pdf.setTitle("{} {}".format(APP_NAME, guide["title"]))
    pdf.setCreator("{} {}".format(APP_NAME, VERSION_LABEL))
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                  QMarginsF(18, 16, 18, 16), QPageLayout.Unit.Millimeter))
    rect = pdf.pageLayout().paintRectPixels(96)
    doc = QTextDocument()
    doc.setDefaultFont(QFont("DejaVu Sans", 10))
    doc.setDefaultStyleSheet("h1, h2 { color: #283593; } h2 { font-size: 17pt; } pre { font-size: 9pt; } "
                             "p, li { line-height: 130%; }")
    doc.setHtml(to_html(guide, rect.width() - 8))
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    doc.print(pdf) if hasattr(doc, "print") else doc.print_(pdf)
    print("wrote", out)


def to_markdown(guide):
    """The same guide as Markdown (docs/manual.md), so both always say the same."""
    import re

    def md(text):
        text = fmt(text)
        text = re.sub(r"</?b>", "**", text)
        text = re.sub(r"</?i>", "*", text)
        text = re.sub(r"</?code>", "`", text)
        return html.unescape(text)
    out = ["# {} {} · {}".format(APP_NAME, guide["title"], VERSION_LABEL), "", md(guide["lead"]), "",
           "The same guide as a PDF with pictures: [{0}]({0}).".format(guide["file"]), "", "## " + guide["toc"], ""]
    out += ["{}. {}".format(n, md(t)) for n, (t, _b) in enumerate(guide["chapters"], 1)]
    for n, (title, body) in enumerate(guide["chapters"], 1):
        out += ["", "## {}. {}".format(n, md(title)), ""]
        for b in body:
            if isinstance(b, str):
                out += [md(b), ""]
            elif b[0] == "list":
                out += ["- " + md(x) for x in b[1]] + [""]
            elif b[0] == "steps":
                out += ["{}. {}".format(i, md(x)) for i, x in enumerate(b[1], 1)] + [""]
            elif b[0] == "code":
                out += ["```sh" if not b[1].lstrip().startswith(("{", "#!", "Types:")) else "```", b[1], "```", ""]
            elif b[0] == "warn":
                out += ["> **WARNING: {}**".format(md(b[1])), ""]
            elif b[0] == "table":
                out += ["| " + " | ".join(md(h) for h in b[1]) + " |", "|" + "---|" * len(b[1])]
                out += ["| " + " | ".join(md(c).replace("|", "\\|") for c in row) + " |" for row in b[2]] + [""]
            elif b[0] == "img":
                out += ["![{}](screenshots/{})".format(md(b[2]), b[1]), ""]
    return "\n".join(out).rstrip() + "\n"


def main():
    from disco.qt.gui import QGuiApplication
    app = QGuiApplication(sys.argv)  # fonts and images need it
    write(EN, ROOT / "docs" / EN["file"])
    app.processEvents()
    (ROOT / "docs" / "manual.md").write_text(to_markdown(EN))
    print("wrote", ROOT / "docs" / "manual.md")


if __name__ == "__main__":
    main()
