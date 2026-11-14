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
    "lead": "Build your own Debian or Devuan distribution for PCs, ARM64, Raspberry Pi and RISC-V.",
    "toc": "Contents",
    "cover": "01-builder.png",
    "chapters": [
        ("What is {app}?", [
            "<b>{app} (Distro Custom)</b> is free and open source software (GPL-3.0-or-later) to build your own "
            "Linux distribution from <b>Debian</b> (stable, testing, sid) or <b>Devuan</b>. It uses Debian's own "
            "tools only: <code>debootstrap</code> or <code>mmdebstrap</code>, <code>chroot</code>, "
            "<code>mksquashfs</code>, <code>xorriso</code> and, if you like, <code>live-build</code>. Nothing of "
            "Ubuntu is used: no casper, no PPAs, no Ubuntu bases.",
            "The result is a <b>hybrid live ISO</b> (BIOS and UEFI) for PCs and UEFI machines, installed with "
            "Calamares, or an <b>SD-card image</b> for the Raspberry Pi. Other processors are built on your "
            "computer through <b>qemu-user</b>.",
            ("table", ["Platform", "Processor", "Kernel package", "Result"], [
                ["PC, 64-bit", "amd64", "linux-image-amd64", "ISO (BIOS + UEFI)"],
                ["Older PC, 32-bit (Debian 12)", "i386", "linux-image-686-pae", "ISO (BIOS + UEFI)"],
                ["ARM 64-bit with UEFI", "arm64", "linux-image-arm64", "ISO (UEFI)"],
                ["Raspberry Pi 3, 4, 400", "arm64", "linux-image-arm64", "SD-card image"],
                ["Raspberry Pi 5 (experimental)", "arm64", "linux-image-arm64", "SD-card image"],
                ["Raspberry Pi 2, 3 (32-bit)", "armhf", "linux-image-armmp", "SD-card image"],
                ["Raspberry Pi 1, Zero, Zero W", "armel", "linux-image-rpi", "SD-card image"],
                ["RISC-V 64 with UEFI (experimental)", "riscv64", "linux-image-riscv64", "ISO (UEFI)"]]),
            "The work is split into <b>ten steps</b> in the sidebar; each step has its pages as tabs. Step 1, the "
            "<b>Builder</b>, can build the whole distribution on its own with <b>Build all</b>; the other steps "
            "refine it.",
            ("list", ["1 Builder · 2 System · 3 Desktop & Apps · 4 Boot · 5 Branding",
                      "6 Look & Feel · 7 Installer · 8 Advanced · 9 Review & Apply · 10 Check & Build"]),
        ]),
        ("Installing {app}", [
            ("steps", ["Install the package and every tool it needs:",
                       "For other processors (ARM64, Raspberry Pi, RISC-V) also install qemu-user and binfmt:",
                       "For the live-build route install Debian's live-build:",
                       "Start {app} from the menu (<b>D!sco</b>) or a terminal."]),
            ("code", "sudo apt install ./disco_0.11_all.deb\n"
                     "sudo apt install qemu-user-static binfmt-support      # ARM and RISC-V\n"
                     "sudo apt install live-build                            # optional\n"
                     "disco                  # the window (asks for the administrator password)\n"
                     "sudo disco --help      # the command line"),
            "Needs Debian 12 or newer (or a derivative), 4 GB of memory and free disk space of about three "
            "times the size of the finished image. The old commands <code>distroforge</code> and "
            "<code>eduka-customizer</code> still open {app}; old settings are read automatically.",
        ]),
        ("Quick start: a distribution in six clicks", [
            ("steps", ["Open <b>1. Builder</b>. Choose a preset, for example <b>Debian Xfce desktop (PC 64-bit)</b> or "
                       "<b>Raspberry Pi desktop</b>, and press <b>Load</b>.",
                       "Type the <b>Distro name</b> and check the <b>Build path</b> (one folder per distribution).",
                       "Tick the package lists you want (double-click a list to add programs from the catalog).",
                       "Press <b>Prepare</b>: {app} checks the choices and this computer and lists what is missing.",
                       "Press <b>Build all</b>. It makes the base system, installs the desktop and the lists, copies "
                       "the overlay, runs your scripts and makes the ISO or SD-card image.",
                       "Test it in QEMU (<b>Test in QEMU</b>) and write it to a USB stick or SD card."]),
            ("img", "01-builder.png", "The Builder: preset, distribution and the build steps"),
        ]),
        ("Step 1 · The Builder", [
            "The Builder holds the whole distribution, like the classic distro builders, in one modern page:",
            ("table", ["Field", "What it is"], [
                ["Preset", "Load, Save, File (import/export), Delete, New. ★ presets come with {app}."],
                ["Distro name", "The name of your distribution (os-release, boot menu, installer)."],
                ["Build path", "The project folder: system, lists, overlay, scripts and output."],
                ["Platform", "What the system is for: PC, ARM64, Raspberry Pi, RISC-V (see chapter 1)."],
                ["Distro base", "Debian or Devuan, and the release: stable, testing, sid or oldstable."],
                ["GUI system", "A desktop (Xfce, GNOME, KDE Plasma, ...), a window manager, or none."],
                ["Init system", "systemd, SysVinit, OpenRC or runit (Devuan: never systemd)."],
                ["Installer", "Calamares, none (live only) or your own .deb packages."],
                ["Method", "D!sco (debootstrap → chroot → squashfs → xorriso) or Debian live-build."],
                ["Repository", "Another Debian or Devuan mirror (default: the Settings page)."]]),
            "The <b>Build</b> card shows the five steps and when each one was last finished. A step can be run "
            "again at any time, for example <b>Install packages</b> after changing a list.",
            ("img", "01b-builder-lists.png", "Package lists with tick boxes"),
            "Under the lists: <b>Edit / view</b> (repositories, overlay folder, scripts, system files), "
            "<b>After the build</b> (QEMU, a terminal in the system, the desktop in a window, Synaptic) and "
            "<b>Tools</b> (open the build folder, unmount everything, delete the build, this guide).",
            ("img", "01c-builder-tools.png", "Edit / view, after the build and tools"),
        ]),
        ("Package lists and the catalog", [
            "Each list is a plain text file in <code>lists/</code> of the build path, installed in the order of its "
            "number. One Debian package per line; <code>#</code> starts a comment and <code>-name</code> removes "
            "a package. Lists that are switched off stay in the folder.",
            ("code", "# Title: Applications\n"
                     "# Programs for the menu: tick them in the catalog or type their names.\n"
                     "firefox-esr\n"
                     "libreoffice\n"
                     "vlc\n"
                     "-nano"),
            "Double-click a list (or press <b>Edit</b>) to tick programs in the catalog: Internet, Office, "
            "Graphics, Audio & Video, Education & Science, Programming, System Tools, Accessories, Games, "
            "Electronics & Raspberry Pi, Accessibility and Network & Server. Packages that your release or "
            "processor does not have are skipped with a note instead of stopping the build.",
            ("img", "01d-list-editor.png", "Editing a list with the catalog"),
        ]),
        ("The build steps in detail", [
            ("steps", ["<b>Prepare</b> writes the first lists, makes the folders <code>lists</code>, "
                       "<code>overlay</code>, <code>hooks</code> and <code>debs</code>, switches qemu-user on for "
                       "other processors and lists every missing tool with the command that installs it.",
                       "<b>Build base</b> makes a new system with mmdebstrap (or debootstrap), checks the Debian "
                       "keyring, gives the system its own host name and empty resolv.conf, switches to the chosen "
                       "init system and writes the name of your distribution.",
                       "<b>Install packages</b> installs the desktop, every list that is on, and the installer.",
                       "<b>Overlay & scripts</b> copies <code>overlay/</code> into the system (owner root) and runs "
                       "every <code>hooks/*.sh</code> inside it, in name order.",
                       "<b>Make image</b> cleans the system, makes the initramfs and builds the ISO or the SD-card "
                       "image."]),
            "What <b>Build base</b> does, by hand:",
            ("code", "sudo mmdebstrap --variant=important --architectures=amd64 \\\n"
                     "    --components=main,contrib,non-free,non-free-firmware \\\n"
                     "    --include=systemd-sysv,live-boot,live-config,linux-image-amd64 \\\n"
                     "    --include=sudo,network-manager \\\n"
                     "    trixie /home/disco/mylinux/rootfs http://deb.debian.org/debian"),
            "The overlay folder mirrors the system: <code>overlay/etc/skel/.bashrc</code> becomes "
            "<code>/etc/skel/.bashrc</code>. A script in <code>hooks/</code> runs as root inside the system:",
            ("code", "#!/bin/sh\n# hooks/20-defaults.sh\nset -e\napt-get install -y --no-install-recommends fastfetch\n"
                     "echo 'fastfetch' >> /etc/skel/.bashrc"),
        ]),
        ("ARM, Raspberry Pi and RISC-V", [
            "On a PC, the programs of an ARM or RISC-V system run through <b>qemu-user</b> with binfmt_misc. "
            "{app} switches it on itself; to check it by hand:",
            ("code", "sudo apt install qemu-user-static binfmt-support\n"
                     "update-binfmts --display qemu-aarch64     # 'enabled', flags include F\n"
                     "ls /proc/sys/fs/binfmt_misc/               # qemu-aarch64, qemu-arm, qemu-riscv64"),
            "<b>Raspberry Pi images</b> are laid out like Debian's own:",
            ("table", ["Partition", "Label", "File system", "Holds"], [
                ["1 (from 4 MiB)", "RASPIFIRM", "FAT32", "firmware, kernel, initrd, device trees, config.txt, "
                                                          "cmdline.txt, sysconf.txt"],
                ["2", "RASPIROOT", "ext4", "the system; grows to the whole card at the first start"]]),
            "Debian's <code>raspi-firmware</code> package writes the boot partition again after every kernel "
            "update. Your own lines are kept: config.txt lines in <code>/etc/default/raspi-firmware-custom</code>, "
            "kernel options in <code>/etc/default/raspi-extra-cmdline</code> (page <b>4. Boot → Raspberry Pi</b>).",
            ("img", "04d-raspberry-pi.png", "The Raspberry Pi page"),
            "At the first start the card grows to its full size, new SSH host keys and a machine id are made, and "
            "<code>sysconf.txt</code> on the boot partition is read (edit it on any computer before the first start):",
            ("code", "hostname=mypi\nroot_authorized_key=ssh-ed25519 AAAA... you@laptop"),
            "Write the card (the image is compressed with xz):",
            ("code", "# find the card, for example /dev/mmcblk0 or /dev/sdb\n"
                     "lsblk\n"
                     "xzcat mylinux-1.0-stable-arm64.img.xz | \\\n"
                     "    sudo dd of=/dev/sdX bs=4M status=progress conv=fsync"),
            ("warn", "dd overwrites the WHOLE device named in of= without asking. Check the name with lsblk "
                     "(unplug and plug the card to see which name appears) and never name the disk of your "
                     "computer. Raspberry Pi Imager (Use custom) and GNOME Disks (Restore Disk Image) are safer."),
            "<b>ARM64 and RISC-V ISOs</b> start with UEFI only: {app} makes GRUB for the processor "
            "(<code>grub-mkstandalone -O arm64-efi</code>, <code>bootaa64.efi</code>) and gives the ISO a GPT with an "
            "EFI partition, so it also starts from a USB stick.",
        ]),
        ("Debian and Devuan repositories", [
            ("table", ["Suite", "Debian", "Devuan", "Notes"], [
                ["oldstable", "bookworm (12)", "daedalus (5)", "32-bit PCs; turn on in Settings for others"],
                ["stable", "trixie (13)", "excalibur (6)", "recommended"],
                ["testing", "forky", "freia", "newer, changes every day"],
                ["unstable", "sid", "ceres", "for developers"]]),
            ("table", ["Repository", "Address"], [
                ["Debian", "http://deb.debian.org/debian"],
                ["Debian security", "http://security.debian.org/debian-security"],
                ["Devuan (all)", "http://deb.devuan.org/merged"],
                ["Debian backports", "http://deb.debian.org/debian (suite trixie-backports)"]]),
            "{app} writes clean deb822 files, for example <code>/etc/apt/sources.list.d/debian.sources</code>:",
            ("code", "Types: deb\nURIs: http://deb.debian.org/debian\nSuites: trixie trixie-updates\n"
                     "Components: main contrib non-free non-free-firmware\n"
                     "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg"),
            "A third-party repository always gets its own key (page <b>2. System → Repositories → Add</b>):",
            ("code", "wget -qO- https://repo.example.org/key.asc | gpg --dearmor | \\\n"
                     "    sudo tee /etc/apt/keyrings/example.gpg >/dev/null\n"
                     "# Signed-By: /etc/apt/keyrings/example.gpg in the .sources file"),
        ]),
        ("The live-build route", [
            "Choose <b>Method: Debian live-build</b> on the Builder (ISO platforms with Debian only). {app} "
            "writes <code>live-build/</code> in the build path and runs it:",
            ("list", ["<code>auto/config</code> — <code>lb config</code> with every choice (release, architecture, "
                      "kernel flavour, archive areas, boot loaders, compression, boot options)",
                      "<code>config/package-lists/*.list.chroot</code> — your lists, the desktop and the live system",
                      "<code>config/includes.chroot/</code> — the overlay folder",
                      "<code>config/hooks/normal/*.hook.chroot</code> — your scripts, the name of the system and the "
                      "packages the lists remove"]),
            "The same by hand (you can change the files first):",
            ("code", "cd /home/disco/mylinux/live-build\nsudo lb clean\nsudo lb config\nsudo lb build"),
            "Debian's live-build of 2021 or later is needed (Debian 11+): {app} checks the version.",
        ]),
        ("Step 2 · System", [
            "Tabs: <b>Repositories</b>, <b>Identity</b>, <b>System files</b>, <b>Users</b>, <b>Language</b> and "
            "<b>Init System</b>.",
            "<b>System files</b> edits the files that tell who the system is. <b>Template from Identity</b> fills "
            "a file from the Identity tab; change it as you like, then <b>Save to the system</b>.",
            ("table", ["File", "Example"], [
                ["/etc/os-release", 'NAME="My Linux" · VERSION="1.0 (Aurora)" · ID=mylinux · '
                                    'PRETTY_NAME="My Linux 1.0 (Aurora)" · HOME_URL=... · LOGO=mylinux-logo'],
                ["/etc/lsb-release", 'DISTRIB_ID="My Linux" · DISTRIB_RELEASE=1.0 · DISTRIB_DESCRIPTION="My Linux 1.0"'],
                ["/etc/issue", "Welcome to My Linux 1.0 - \\n \\l"],
                ["/etc/issue.net", "Welcome to My Linux 1.0"],
                ["/etc/hostname, /etc/hosts", "mylinux · 127.0.1.1 mylinux"],
                ["/etc/motd", "the message after logging in"]]),
            ("img", "02c-system-files.png", "System files"),
            "Below: the <b>picture of new users</b> (<code>/etc/skel/.face</code>, also the login screen's default "
            "picture), <b>settings folders</b> copied from this computer into /etc/skel (for example "
            "<code>~/.config/xfce4</code>: panels and shortcuts; caches and keys stay out) and the <b>GRUB "
            "background</b> of installed computers (GRUB_BACKGROUND; the installer runs update-grub).",
            "<b>Init System</b>: systemd, SysVinit, OpenRC or runit with elogind, the right live-config backend and "
            "init scripts; the installer follows. GNOME needs systemd.",
        ]),
        ("Step 3 · Desktop & Apps", [
            "<b>Desktop</b>: a desktop or window manager in a Mini, Compact, Full or Full-with-apps edition; the "
            "login screen, X11 or Wayland and the compositor follow it. <b>Packages</b>: every package of the "
            "system. <b>Flatpak</b>: Flathub applications by category. <b>Replace Apps</b>: another browser, mail "
            "program, editor or terminal for everyone.",
            ("img", "03-desktop.png", "Desktops and editions"),
        ]),
        ("Step 4 · Boot", [
            "<b>Kernel</b>: Debian kernels, backports or third-party kernels (paste their instructions into the "
            "kernel terminal), firmware and the initramfs. <b>Boot Loader</b>: what installed computers start with "
            "(GRUB, GRUB with Secure Boot, systemd-boot, rEFInd, EFISTUB, Syslinux). <b>Boot Menu</b>: the menu of "
            "the ISO (title, timeout, background, GRUB theme, menu designer). <b>Raspberry Pi</b>: see chapter 7.",
            ("img", "04b-boot-loader.png", "Boot loaders of installed systems"),
            "A broken or missing initramfs is made again with:",
            ("code", "sudo disco run update-initramfs -c -k all"),
        ]),
        ("Step 5 · Branding", [
            "<b>Distro Branding</b> builds a package with your logo and name everywhere (base-files, lsb-release, "
            "desktop-base, logos, GRUB, Calamares). <b>Wallpaper & Login</b>: wallpapers and the LightDM greeter "
            "(<code>/etc/lightdm/lightdm-gtk-greeter.conf</code>: background, theme-name, icon-theme-name, "
            "default-user-image), SDDM and GDM. <b>Plymouth</b>: install, preview or make a boot splash from your "
            "logo; by hand:",
            ("code", "sudo disco run plymouth-set-default-theme -R mytheme"),
            "<b>Desktop document</b>: a PDF about your system with the title you like. <b>Write a first text</b> "
            "describes the system from the project; change it freely. It is put into "
            "<code>/usr/share/doc/ID-guide/</code>, on every user's desktop at the first login (in the desktop "
            "folder of the user's language) and in the menu.",
            ("img", "05d-desktop-document.png", "Desktop document"),
        ]),
        ("Step 6 · Look & Feel", [
            "<b>Themes & Icons</b>, <b>System Sounds</b>, <b>Welcome Screen</b> and <b>Terminal & Browser</b>.",
            "<b>Terminal & Browser</b>: the message after login (a fixed <code>/etc/motd</code> or a dynamic script "
            "in <code>/etc/update-motd.d</code>), the bash prompt of every user (<code>/etc/bash.bashrc</code> and "
            "<code>/etc/skel/.bashrc</code>) and the policies of Firefox ESR and Chromium:",
            ("code", '{\n  "policies": {\n    "Homepage": {"URL": "https://mylinux.example.org", "Locked": false},\n'
                     '    "Bookmarks": [{"Title": "Debian", "URL": "https://www.debian.org",\n'
                     '                   "Placement": "toolbar"}],\n'
                     '    "DisableTelemetry": true\n  }\n}'),
            "The file is written to <code>/etc/firefox-esr/policies/policies.json</code>, "
            "<code>/etc/firefox/policies/policies.json</code> and "
            "<code>/usr/lib/firefox-esr/distribution/policies.json</code>; Chromium's to "
            "<code>/etc/chromium/policies/managed/disco.json</code>.",
            ("img", "06b-terminal-browser.png", "Terminal & Browser"),
        ]),
        ("Step 7 · Installer", [
            "<b>Which installer</b>: Calamares (recommended), none (a live system only) or <b>your own .deb "
            "packages</b>: drop them on the page, they are kept in <code>debs/</code> and installed with their "
            "dependencies. Then the Calamares settings: name, images, colors, slides, users, partitions and "
            "<b>Check the installer</b>.",
            ("img", "07-installer.png", "Installer"),
        ]),
        ("Steps 8 to 10 · Advanced, Review & Apply, Check & Build", [
            "<b>Advanced</b>: a terminal inside the system, the desktop in a window (Xephyr), hooks, recipes and the "
            "Package Workshop.",
            "<b>Review & Apply</b>: changes of steps 2 to 8 wait here; tick them, try them in a preview, then "
            "apply them all at once. <b>Build all</b> on the Builder offers to apply them first.",
            ("img", "09-review-apply.png", "Review & Apply"),
            "<b>Check & Build</b>: checks what would break the image (double-click a row to open its page, or "
            "<b>Fix automatically</b>), the target size, compression and the resources of this computer, then "
            "the ISO.",
        ]),
        ("Testing and writing the ISO", [
            "<b>Test in QEMU</b> starts a PC ISO with BIOS, UEFI or Secure Boot, an ARM64 ISO with UEFI, and an "
            "SD-card image with its own kernel (ARM is emulated on a PC: be patient).",
            ("code", "lsblk                     # find the USB stick, for example /dev/sdb\n"
                     "sudo dd if=mylinux-1.0-stable-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync"),
            ("warn", "dd erases everything on the device named in of=. A wrong letter erases your own disk: check "
                     "it with lsblk first."),
        ]),
        ("Command line", [
            "Every step also works in a terminal:",
            ("code", "sudo disco new --preset \"Raspberry Pi desktop (Pi 3, 4, 400)\" /home/disco/mypi\n"
                     "cd /home/disco/mypi\n"
                     "sudo disco builder --name \"My Pi Linux\" --desktop xfce\n"
                     "sudo disco lists show\n"
                     "sudo disco lists add applications thonny python3-gpiozero\n"
                     "sudo disco step prepare\n"
                     "sudo disco build-all\n"
                     "sudo disco test\n"
                     "disco platforms          # what D!sco builds for\n"
                     "disco presets            # the presets\n"
                     "sudo disco live-build export   # write the live-build configuration only"),
            "<code>disco --help</code> lists every command; <code>disco COMMAND --help</code> explains one.",
        ]),
        ("Troubleshooting", [
            ("table", ["Problem", "What to do"], [
                ["NO_PUBKEY / signature errors from APT", "Install the keyring of the repository (Debian: "
                 "debian-archive-keyring, Devuan: devuan-keyring) and use Signed-By in its .sources file."],
                ["Kernel panic or 'Unable to find a medium' at live boot", "live-boot or the initramfs is missing: "
                 "Install packages, then rebuild (Check & Build fixes it automatically)."],
                ["initrd.img-VERSION is missing", "disco run update-initramfs -c -k VERSION"],
                ["ARM ISO does not start from USB", "Built before 0.11: rebuild; the ISO now has a GPT EFI partition."],
                ["Exec format error in the chroot", "qemu-user is not registered: sudo apt install "
                 "qemu-user-static binfmt-support, then Prepare again."],
                ["raspi-firmware did not write the boot partition", "{app} writes it the same way and says so in "
                 "the log; check that raspi-firmware is in the image (non-free-firmware)."],
                ["The system is still in use", "Close the terminal or live session of the system, or Tools → "
                 "Unmount everything."]]),
            "Every message is in the log panel and in <code>/tmp/disco/disco.log</code>. <b>Send feedback</b> sends "
            "a report with screenshots and, if you agree, the logs.",
        ]),
        ("Cleaning up", [
            "The build folders are big. <b>Delete the build (keep ISO/IMG)</b> on the Builder (or closing the "
            "window after a build, or <code>sudo disco clean --keep-iso</code>) deletes everything of the project "
            "but the images and their checksums. Nothing is deleted while anything is mounted inside the project.",
            ("warn", "Never delete a project folder with rm -rf while a terminal or live session of it is open: "
                     "/dev and /proc of your computer are mounted inside it. Use Unmount everything (or sudo disco "
                     "clean) first."),
        ]),
        ("License, trademarks and support", [
            "{app} is free software under the GNU General Public License version 3 or later, WITHOUT ANY WARRANTY. "
            "The licenses of its components are on the <b>About</b> tab. The packages in your distribution keep "
            "their own licenses (<code>/usr/share/doc/PACKAGE/copyright</code>).",
            "Debian is a registered trademark of Software in the Public Interest, Inc.; Raspberry Pi is a trademark "
            "of Raspberry Pi Ltd; Linux® is the registered trademark of Linus Torvalds. {app} is not affiliated "
            "with them. Give your distribution a name and logo of its own.",
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
    app = QGuiApplication(sys.argv)  # noqa: F841 (fonts and images need it)
    write(EN, ROOT / "docs" / EN["file"])
    (ROOT / "docs" / "manual.md").write_text(to_markdown(EN))
    print("wrote", ROOT / "docs" / "manual.md")


if __name__ == "__main__":
    main()
