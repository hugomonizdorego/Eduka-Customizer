# DistroForge manual

Version 0.9 Beta. DistroForge builds live ISO images of any Debian-based
distribution; nothing is preset for a particular distribution. It was called
Eduka-Customizer until 0.17 Alpha. The user guide with pictures is `docs/DistroForge-Guide.pdf`,
installed in
`/usr/share/distroforge/guide/`.

## Concepts

**Project.** A folder that holds everything for one image:

```
project.json   state, settings and history of the project
rootfs/        the root filesystem of the image (what becomes filesystem.squashfs)
iso/           the files of the ISO except the squashfs (boot loader, /live, /.disk)
boot/          boot images copied from the source ISO (MBR template, ...)
hooks/         your scripts, run inside the image in name order
cache/         Eduka-Desktop source, EFI work files, QEMU disks
downloads/     Debian ISOs downloaded by the GUI
output/        built ISO images and checksum files
logs/          distroforge.log, live-session.log, qemu.log
```

Only one DistroForge instance can use a project at a time.

**Supported systems.** Images: Debian stable, testing and sid and every Debian
derivative (`ID_LIKE=debian`) such as LMDE. Ubuntu-based systems are refused.
Recommended source: the Debian live *standard* ISO (no desktop).
Build computer: Debian, a Debian derivative, Ubuntu or an Ubuntu-based system.
The check reads `/etc/os-release`, `/etc/debian_version` and the APT sources
of the image. Ubuntu and every Ubuntu derivative are refused. Debian oldstable is refused unless
`allow_oldstable = yes` is set. Debian codenames live in
`/etc/distroforge/distroforge.conf` (or the Settings page): update
them when Debian makes a new release.

**Chroot.** Commands run inside the image with `chroot`. DistroForge
mounts `/proc`, `/sys`, `/dev` (recursive bind, made a *slave* so nothing
propagates back to your computer) and a private `/run`, copies your DNS
settings, and blocks services from starting (`policy-rc.d`). Mounts are
shared between the GUI, terminals and the CLI and are removed when the last
user leaves. *Terminal & Live → Unmount everything* or
`distroforge clean --unmount-only` recovers after a crash.

## Pages of the GUI

The sidebar lists 13 numbered steps in the order of the work, from the source
of the image to the finished ISO. Pages that are used together share one step
as tabs:

| Step | Tabs |
|---|---|
| 1. Start | Project |
| 2. Repositories | |
| 3. Identity & Branding | Identity, Distro Branding |
| 4. Users | |
| 5. Language | |
| 6. Desktop | |
| 7. Software | Packages, Flatpak apps, Replace apps |
| 8. Kernel & Boot | Kernel, Boot Loader, Boot Menu |
| 9. Look & Feel | Themes & Icons, Wallpaper & Login, Plymouth, System Sounds, Welcome Screen |
| 10. Installer | Calamares |
| 11. Advanced | Terminal & Live, Package Workshop |
| 12. Review & Apply | |
| 13. Check & Build | |
| Settings & About | Settings, About |

The header shows *Step N of 13* and how many steps are done.

**Step by step.** A step opens when the step before it is done: press
**Done — next step** at the bottom (✔ marks the done steps; *Back* goes to the
previous one). Step 1 is done when the project has a system. Quick Wizard and
Settings are always open. The Quick Wizard opens every step when it finishes;
projects made before 0.15 keep every step open. Settings → **Free navigation
(expert mode)** opens every menu at any time.

### 1. Start / Project
Create or open a project, then pick the source:

* **Debian / Debian-based ISO** – any `debian-live-*.iso` or the live ISO of a Debian derivative.
  Ubuntu (`/casper`) images are refused before extraction.
* **Download Debian** – lists the official live images for stable or testing
  (weekly builds), downloads with resume, verifies SHA256 and, when
  `gpgv` and `debian-keyring` are installed, the signature of `SHA256SUMS`.
* **New Debian base** – `mmdebstrap` (or `debootstrap`) with live-boot,
  live-config, kernel, firmware, NetworkManager and Plymouth. Then install a
  desktop on the Desktop page.
* **This computer** – remastersys / penguins-eggs style snapshot.
  *Distribution* removes user accounts and `/home`; *Backup* keeps them.

When an ISO is extracted, its El Torito/MBR/GPT boot setup is recorded with
`xorriso -report_el_torito as_mkisofs` and the needed byte ranges are copied
into `boot/`, so the rebuilt ISO boots exactly like the original even after
the source ISO is deleted ("replay" boot mode).

#### What is your distribution for?
When a project gets its system (an ISO is extracted or downloaded, or a new
Debian base is made), a window asks what the distribution is for:

| Purpose | Recommended |
|---|---|
| Education | Xfce with xfwm4, LightDM, Papirus + Arc, LibreOffice, Firefox, GCompris, KGeography, Kalzium, Stellarium, Tux Paint, TuxMath, Marble, KTurtle, Orca, Onboard, VLC; GeoGebra (Flatpak) |
| Server | no desktop; OpenSSH server, ufw, fail2ban, unattended-upgrades, htop, curl, rsync, vim, tmux |
| Professional | KDE Plasma (Wayland) with KWin, SDDM, Breeze, LibreOffice, Thunderbird, Okular, GIMP, Inkscape, Krita, VLC, Remmina, KeePassXC, git |
| Home | Cinnamon with Muffin, LightDM Slick greeter, Papirus + Arc, Firefox, Thunderbird, LibreOffice, VLC, Rhythmbox, Shotwell, Transmission, games |
| Other | nothing: build it yourself |

Choose the **ISO edition** too:

* **Minimal** – the desktop in its *Mini* edition, firmware and the installer;
  no extra applications, no Flatpak, no splash (Server: OpenSSH, ufw and
  unattended-upgrades only).
* **Full** – the *Full* desktop and the applications of the purpose.
* **Full with recommended apps** – *Full with apps* desktop, the applications of
  the purpose and its Flatpak apps (the largest ISO).

Firmware, the Calamares installer and a Plymouth splash are recommended
where they make sense. Untick what you do not want and press *Apply*, or
close the window. *What is it for?* on the Start page opens it again. The
purposes are stored in `data/profiles.json`.

### Quick Wizard
Eight steps — Source, Identity, Base system, Desktop, Look, Applications,
Branding, Finish. Every answer becomes a recipe step; the last page shows the
recipe. Finish creates or opens the project, extracts the ISO or bootstraps
Debian, runs every step and (optionally) builds the ISO. The recipe is saved as
`PROJECT/recipe-wizard.json` so the build can be repeated with
`distroforge recipe apply`.

### 2. Repositories
* Suite presets write `/etc/apt/sources.list.d/debian.sources` (deb822)
  with `main contrib non-free non-free-firmware`, updates, security and
  optionally backports and `deb-src`. Old Debian entries are kept as
  `*.eduka-old`.
* Moving to a newer suite: apply, then *Packages → Upgrade all*. Moving back
  to an older suite is not supported by APT.
* *Add repository* stores the key under `/etc/apt/keyrings/NAME.gpg` and
  references it with `Signed-By`.
* Every `.list`/`.sources` file can be edited directly.

### 3. Identity & Branding → Identity
The fields start with what the extracted ISO says about itself (os-release, host name, volume label);
*Reload from the ISO* fills them again. Distro Branding likewise loads the ISO's logo, wallpaper,
login and GRUB backgrounds and installer colors (copied to `PROJECT/from-iso/`).
* os-release: `NAME`, `PRETTY_NAME`, `VERSION`, `ID=mylinux`,
  `ID_LIKE=debian`. `VERSION_CODENAME` stays the Debian codename because APT
  tooling uses it; your codename is stored as `DISTRO_CODENAME`.
  `/usr/lib/os-release` is protected with `dpkg-divert` so `base-files`
  upgrades do not undo it.
* `/etc/issue`, `/etc/issue.net`, `/etc/lsb-release`, `/etc/hostname`, `/etc/hosts`.
* Computer name (`/etc/hostname`, `/etc/hosts` and the live session). The live
  user and passwords are on the Users page.
* Calamares branding (`/etc/calamares/branding/*/branding.desc`).

### 3. Identity & Branding → Distro Branding
Turns Debian into your own distribution without patching Debian's packages.
It generates a Debian source package `PROJECT/branding/<id>-branding/`
(`debian/control`, `changelog`, `copyright`, `rules`, `<id>-branding.install`,
`postinst`, `prerm` and a `files/` tree), builds it with `dpkg-deb` and
installs it into the image. Its `postinst` uses `dpkg-divert` so Debian's
files move to `*.distrib` and yours take their place:

| Debian package | What is replaced |
|---|---|
| base-files | `/usr/lib/os-release` (`ID=<id>`, `ID_LIKE=debian`, `LOGO=<id>-logo`), `/etc/issue`, `/etc/issue.net` |
| lsb-release | `/etc/lsb-release`; `lsb_release -a` reads os-release |
| distro-info-data | `/usr/share/distro-info/<id>.csv` is added |
| desktop-base | wallpaper, login and GRUB images registered as `desktop-background`, `desktop-grub`, ... alternatives |
| Debian logos | every Debian logo found in the image (desktop-base, icon themes, Plymouth) is re-rendered from your logo in the same size and format |
| grub | `/etc/default/grub.d/90-<id>.cfg`: name, background, timeout, `quiet splash` |
| calamares-settings-debian | `/etc/calamares/branding/<id>/` (logo, colors, slideshow) and `settings.conf` |
| debian-archive-keyring | optional `<id>-archive-keyring` with your own ed25519 key (back it up!) |

`/etc/debian_version` stays: many tools need it to know they run on Debian.
`VERSION_CODENAME` stays the Debian codename for the same reason.

*Secure Boot*: Debian's signed GRUB reads `EFI/debian/grub.cfg`. With
"Keep Secure Boot working" a small hook copies GRUB's configuration there when
the EFI folder carries your name, and Calamares installs with the EFI id
`debian`.

Edit any file in "Edit the packages directly", then *Build and install edited
source*. Debian updates keep your branding; removing the package gives Debian
its files back.

### 4. Users
* **Live user** – the account that logs in when the ISO starts. live-config
  creates it at every boot; Debian's default is `user` with the password
  `live`. Choose the user name, full name, groups, automatic login and the
  password: Debian's default, **your own password** (stored as a SHA-512
  hash in a live-config script) or **no password at all** (`passwd -d`, the
  user logs in without a password). *Remove* returns to Debian's defaults.
  Files: `/etc/live/config.conf.d/50-eduka-customizer.conf` and
  `/usr/lib/live/config/1999-eduka-password`.
* **Accounts in the image** – real accounts inside the root filesystem, for
  example an administrator account: create them with or without a
  password and optionally as administrators (`sudo`), change or remove the
  password, or delete them with their home folder. They exist in the live
  session and on every computer installed from the ISO.
* The computer name is set on the Identity page; the rules for the accounts
  the installer creates are on the Calamares page.

### 5. Language
The default language of the live session, the installer and the installed
system. The same choice is offered on the Start page when a project is
created from an ISO, a download or a new Debian base.

* Locale (`locale-gen`, `/etc/default/locale`), time zone (Asia/Dili by default; `tzdata` is
  installed when missing; choosing a language does not change it), keyboard layout and variant (`/etc/default/keyboard`;
  several layouts such as `us,ru` switch with Alt+Shift), all passed to
  live-config too (`/etc/live/config.conf.d/40-eduka-customizer-locale.conf`).
* **Translations and spell checking**: hunspell and hyphenation dictionaries,
  and the translations of LibreOffice, Firefox and Thunderbird — only for the
  programs already installed, so nothing big is pulled in. CJK languages get
  Noto CJK fonts and fcitx5 input. Packages missing in the Debian release are
  skipped and listed in the log. Catalog: `data/languages.json`.
* **Boot menu**: with more than one language ticked, a *Language* submenu is added to GRUB and ISOLINUX; every entry starts the live
  system with `locales=`, `keyboard-layouts=` and the chosen `timezone=`.
  It is re-created at every build.
* **Calamares**: the installer's time zone (`locale.conf`) follows the
  choice and GeoIP is switched off; the installer's language follows the
  live session.

Tetun has no glibc locale yet; for Timor-Leste use `pt_PT.UTF-8` and
`en_US.UTF-8`.

### 6. Desktop
* Install one of the desktops or window managers from
  `/usr/share/distroforge/desktops.json` (edit it to add more). Only what
  Debian ships is listed: GNOME, KDE Plasma, Xfce, Cinnamon, MATE, LXQt, LXDE,
  Budgie, GNOME Flashback, Enlightenment, Eduka-Desktop, and the window
  managers Openbox, i3, Fluxbox, IceWM, awesome, JWM, herbstluftwm, bspwm, dwm,
  spectrwm, Sway, labwc, Wayfire and Hyprland (Debian 13 and newer).
  *Remove other Debian desktop tasks* purges the others.
* **Edition** of the install:
  * **Mini** – the desktop or window manager, a terminal and a file manager,
    without recommended packages.
  * **Compact** – the desktop with its core tools, network and settings, still
    without recommended packages.
  * **Full** – the complete desktop as Debian ships it (the `task-*-desktop`
    package with its recommended packages).
  * **Full with apps** – Full plus the recommended applications for the
    desktop (browser, office, mail, media, graphics; GTK, GNOME, KDE, Qt or
    light sets). Applications a Debian suite does not have are skipped.
* **Eduka-Desktop** is fetched from git (any branch or tag, or a local
  folder), built into a `.deb` with `dpkg-deb --root-owner-group` (or
  `dpkg-buildpackage` if the repository gets a `debian/` folder), and
  installed with APT so its dependencies are pulled in.
* **Eduka-Desktop defaults** are read from the installed
  `eduka_common.py` (so new settings of future versions appear
  automatically) and written to `/etc/skel/.config/eduka-desktop/`.
* **Login screen**: LightDM with the GTK, Slick, Arctica or KDE greeter,
  SDDM (with theme choice), GDM, LXDM, Ly or greetd + tuigreet. *Check
  availability* disables the ones the image's Debian suite does not have.
* **Compositors that fit the desktop**: the desktop's own compositor —
  Mutter (GNOME), Muffin (Cinnamon), KWin (KDE), xfwm4 (Xfce), Marco (MATE),
  Budgie's window manager — is recommended. picom and xcompmgr are not
  offered for desktops that always composite (GNOME, Cinnamon, KDE, Budgie)
  and their autostart entries get `NotShowIn=` for those desktops, so two
  compositors never run at once. On Wayland, GNOME and KDE are their own
  compositor; only LXQt lets you choose (labwc, KWin, Wayfire, Sway).
* **Session type and compositor**: X11 or Wayland for desktops that offer
  both (GDM and SDDM are configured to match). Compositors for X11: picom
  with presets (light, shadows, glass blur for Eduka-Desktop Liquid Glass,
  off), xcompmgr, the desktop's built-in compositor, or none. For Wayland
  (LXQt): labwc, KWin, Wayfire or Sway.
* Default session for the login manager, live autologin and
  `x-session-manager`; window manager used by LXQt/Eduka-Desktop.

### 7. Software → Packages
* **All Debian packages** of the image's sources, read directly from
  `/var/lib/apt/lists` (press *Refresh package lists* first if the ISO has
  none). Views: *Applications* (no libraries), *All packages*, *Installed*,
  *My changes*, plus Debian sections. Search runs as you type over names and
  descriptions. Ticked = in the ISO: tick to install, untick to remove;
  required and important packages cannot be unticked. *Apply changes*
  removes and installs in one go.
* **Remove applications of the ISO** lists every installed program with a
  menu entry (from its `.desktop` file) and the package that owns it.
* Other ways: type names and press *Tick*, import/export a package list,
  Synaptic in a window or a terminal (Terminal & Live), or right before
  building (Build & Test).

* Maintenance: full upgrade, autoremove, local `.deb` files (dependencies
  are resolved by APT). Package lists: `name` installs, `-name` removes.

### 7. Software → Flatpak apps
The whole Flathub catalog by category (Productivity & Office, Audio & Video, Graphics & Photography,
Networking & Internet, Education, Science, Games, Developer Tools, System, Utilities). *Update from
Flathub* fetches it from the Flathub API, or else Flathub's AppStream data through flatpak in the
image; it is kept in `PROJECT/cache/flathub-catalog.json`. Filter, tick, *Add ticked apps*.
*Enable Flatpak + Flathub* installs `flatpak` (and the Discover/GNOME
Software plugin when present) and adds Flathub system-wide. Apps can be
installed into the image now, or listed for installation on the **first boot
of the installed system** (a systemd unit that waits for the network and
skips the live session). The second option keeps the ISO small.

### 7. Software → Replace apps
Every desktop brings its own programs. For each kind — web browser, e-mail,
word processor, spreadsheet, text editor, file manager, terminal, image
viewer, video player, music player, PDF viewer, archive manager, calculator —
choose another Debian package (or type any name). It is installed, becomes the
default **for everyone** (every user of the live and installed system; also the Xfce
helpers, KDE kdeglobals, LXQt session and GNOME/Cinnamon/MATE terminal settings and
the lists in /etc/skel) for its file types in `/etc/xdg/mimeapps.list` (and in the desktop's
own `/etc/xdg/*-mimeapps.list`), and for its Debian alternatives
(`x-www-browser`, `gnome-www-browser`, `x-terminal-emulator`, `editor`). Tick
*Remove the programs of this kind that are installed now* to remove the old
ones. When removing a program would take a metapackage (`task-gnome-desktop`,
`kde-standard`, ...) with it, everything that metapackage installed is marked
as manually installed first, so `autoremove` never removes the desktop. The
roles live in `/usr/share/distroforge/apps.json`. CLI:
`distroforge apps roles|status|replace ROLE PACKAGE [--remove-old]`.

### 8. Kernel & Boot → Kernel
**Third-party repository terminal**: commands run as root inside the image (for example the key and
`deb` line from a kernel's website, then `apt update`). Repository files and keys created there are
temporary; the kernels of those repositories are listed. Installing one keeps its repository and key;
the others are removed with their package lists (*Keep or remove now*, at the latest by the build).
* Table of installed kernels: package, origin, size, initrd, headers, the
  kernel the ISO boots (●) and holds. The metapackage line tells which package
  keeps kernels up to date.
* **Install**: Debian kernels (signed for Secure Boot) with optional headers;
  **backports** (adds `<codename>-backports` and installs with `-t`);
  **Liquorix** and **XanMod** (repository and key are added, amd64 only, not
  signed for Secure Boot); **your own repository** (URI, suite, components,
  key file or URL, packages); or **.deb files** (e.g. a self-built kernel).
* **Remove** a kernel (image, headers and modules packages, or the files of a
  kernel copied by hand). The last kernel cannot be removed.
* **Hold / unhold**, **Update initramfs**, **Use for the ISO**, **Copy to the
  ISO now**.
* **GRUB of the installed system**: its settings are on the Boot Loader tab. *Run update-grub* only
  works in an image that already has an installed GRUB menu.
* **Drivers**: install common firmware (needs `non-free-firmware`) and
  rebuild DKMS modules for every kernel.

### 8. Kernel & Boot → Boot Loader
The boot loader that installed computers start with. The table lists every boot loader with the
computers it works on, whether it is installed in the image and which one the installer uses.

| Boot loader | Computers | Installed by | Settings |
|---|---|---|---|
| GRUB 2 | BIOS and UEFI | Calamares (`efiBootLoader: grub`) | timeout, kernel options, menu (shown, countdown, hidden), default entry (first or last chosen), os-prober, recovery entries, resolution — written to `/etc/default/grub.d/95-eduka-customizer.cfg` |
| GRUB 2 with Secure Boot | BIOS and UEFI | Calamares (`sb-shim`) | as GRUB 2 |
| systemd-boot | UEFI | Calamares (`systemd-boot`), then DistroForge's step | timeout, kernel options, default entry (newest or last chosen), editor, screen mode — `loader/loader.conf` on the EFI partition |
| rEFInd | UEFI | Calamares 3.3 (`refind`), then DistroForge's step | timeout, kernel options, resolution, text mode, tools row — `refind.conf`, `/boot/refind_linux.conf` |
| EFISTUB | UEFI, Secure Boot off | DistroForge's step | kernel options, name in the firmware menu — a UEFI boot entry (`efibootmgr`) that starts `\EFI\<id>\vmlinuz.efi` |
| Syslinux / EXTLINUX | BIOS | DistroForge's step | timeout, kernel options, menu title, graphical menu — `/boot/syslinux/syslinux.cfg`, MBR or GPT boot code |

* **Install into the image** installs the Debian packages (grub-pc-bin + grub-efi-amd64-bin, shim-signed,
  systemd-boot, refind, efibootmgr, extlinux + syslinux-common + fdisk). **Remove from the image** purges
  them; it never removes the boot loader in use, and stops when other packages would go with it.
* **Use for installed systems** installs it when needed, writes `/etc/distroforge-bootloader.conf` and
  points the installer at it. For EFISTUB and Syslinux the `bootloader` module in the sequence of
  `settings.conf` is replaced by `shellprocess@distroforge-bootloader` (configuration
  `modules/shellprocess-distroforge-bootloader.conf`), which runs `/usr/sbin/distroforge-bootloader install`
  in the new system; for systemd-boot and rEFInd that step runs after Calamares' module and adds the
  settings. Choosing GRUB again puts the `bootloader` module back.
* **Fallbacks**, so the installation does not stop with an error: EFISTUB on a BIOS computer uses
  Syslinux (when installed) or GRUB; Syslinux on a UEFI computer, or with /boot on LVM, encrypted or not
  ext2/3/4/FAT, uses EFISTUB or GRUB. Debian live ISOs install GRUB from their pool, so GRUB is there.
* Kernel and initramfs hooks (`/etc/kernel/postinst.d`, `postrm.d`, `/etc/initramfs/post-update.d`) copy
  new kernels to the EFI partition (EFISTUB) or write the Syslinux menu again; they do nothing in the live
  system or the image.
* The installer check and Check & Build check the step, its configuration and the tools it needs;
  *Fix automatically* sets the boot loader up again or installs what is missing.
* Tested in QEMU: Syslinux on MBR and GPT disks (SeaBIOS) and EFISTUB (OVMF) start the kernel with the
  options set here.
* LILO and BURG are listed but cannot be chosen: they are no longer developed and not in Debian.

### 8. Kernel & Boot → Boot Menu
* Menu settings: title, timeout, kernel options (e.g. `quiet splash`,
  `toram`, `nomodeset`), kernel version and background image.
* **Edit boot files**: `boot/grub/*.cfg`, `isolinux/*.cfg` and the `.cfg`
  files inside `boot/grub/efi.img` (read and written with mtools), shown as
  `efi.img:EFI/boot/grub.cfg`. *Check* runs `grub-script-check` and looks for
  missing kernels, initrds and includes.
* A saved file is kept in `PROJECT/boot-overrides/` and copied over the menu
  at every build (marked ✎), so a regenerated menu never loses it. The first
  version is kept in `PROJECT/boot-originals/` for *Revert to original*.
* **Save and apply to the ISO now** rebuilds the ISO in seconds with the
  compressed system of the last build (also *Rebuild boot files only* on
  Build & Test, `distroforge bootmenu apply`).
* **GRUB theme**: drop a theme folder or archive (with `theme.txt`). It is checked first and refused
  with the reasons when GRUB could not show it: no theme.txt, pictures GRUB cannot read (only PNG,
  JPEG and TGA), files theme.txt names that are missing (also `*_pixmap_style` patterns), TTF/OTF
  instead of .pf2 fonts, files outside the theme, more than 25 MiB. Accepted themes go to the ISO
  (`/boot/grub/themes/<name>`, used by the UEFI menu; the BIOS menu is ISOLINUX) and optionally to
  installed systems (`GRUB_THEME` in `/etc/default/grub.d/96-eduka-grub-theme.cfg`). Builds keep it.
* **Menu designer**: the entries of `/boot/grub/grub.cfg` — rename (double-click), reorder, remove,
  add ready-made entries (live, safe graphics, copy to RAM, boot messages, fail-safe, UEFI firmware
  settings, restart, power off), the default entry, the timeout and colors. Saved as a kept edit.

### 9. Look & Feel → Themes & Icons
Only what fits the desktop chosen in step 6 is listed (all of it while none is chosen): theme packs
from `/usr/share/distroforge/themes.json` (for all desktops, GTK desktops and window managers,
Qt desktops, or one desktop), the GTK theme (for GTK applications on KDE/LXQt), the LXQt theme, and
the window theme of Xfwm4, Openbox, Cinnamon, Marco/Metacity, the Plasma global theme and Kvantum.
* **Add your own**: drop folders, archives or files. Recognized and placed:
  GTK themes (`index.theme` with gtk-3.0/gtk-4.0/xfwm4/cinnamon/...) in
  `/usr/share/themes`; icon themes (`[Icon Theme]` with `Directories`) and
  cursor themes (`cursors/`) in `/usr/share/icons` (icon cache updated);
  fonts (.ttf, .otf, .ttc) in `/usr/share/fonts/*/eduka-custom` (fc-cache);
  Plymouth themes; SDDM themes (`metadata.desktop` + QML) in
  `/usr/share/sddm/themes`; pictures to the wallpaper gallery; `.deb` files
  are installed. Archives are checked: absolute paths, devices and links
  pointing outside the archive are refused.

* **Default look**: GTK theme, icons, cursor, LXQt/Eduka theme, font and dark style,
written for GTK 2/3/4, GNOME, Cinnamon, MATE (gsettings overrides), LXQt and
Eduka-Desktop, Xfce and KDE. One-click theme packs (only those available for
the image's Debian suite are installed), import of theme archives or folders,
and desktop icons for LXQt/Eduka-Desktop and Xfce.

### 9. Look & Feel → Wallpaper & Login
* **Wallpaper gallery** in `/usr/share/backgrounds/<id>/`: drop pictures or
  folders, *Make default ★* (applied to every desktop), *Remove*. All
  pictures are listed for the wallpaper choosers of GNOME, Cinnamon and
  MATE (`*-background-properties/<id>.xml`).

* The default wallpaper is set for LXQt/Eduka-Desktop (pcmanfm-qt), Xfce, KDE Plasma, GNOME,
  Cinnamon, MATE and Debian's `desktop-background` alternative.
* Login screen: background, logo, GTK and icon theme for LightDM greeters,
  SDDM theme and background, GDM logo, LXDM background.

### 9. Look & Feel → Plymouth
* List of installed themes with type, package and a preview image.
* **Install** from a Debian package (`.deb`), an archive (`.zip`, `.tar.gz`,
  `.tar.xz`, `.tar.bz2`), a folder or a `.plymouth` file — themes from
  gnome-look/pling usually come as archives — or tick Debian's
  `plymouth-theme-*` packages. Archives are checked for unsafe paths, and
  `ImageDir`/`ScriptFile` are fixed to the installed location.
* **Preview in a window**: runs `plymouthd` with the X11 renderer
  (`plymouth-x11`, installed when needed) inside a Xephyr window, shows
  progress, messages and a password prompt, then restores the previous theme.
* **Apply** (`plymouth-set-default-theme`, or `plymouthd.conf` where that
  tool does not exist), **Remove** (imported themes are deleted, packaged
  themes are purged; the current theme and themes inside `plymouth-themes`
  are protected), **Create from a logo**.
* Settings: delay before the splash, HiDPI scale, splash on ISO boot.

### 9. Look & Feel → System Sounds
Sounds for **boot**, **startup (login)**, **log out**, **shutdown**, **error**, **warning**,
**information**, **question**, new message / e-mail, task complete, bell, device connected /
removed, power cable, battery low, trash, screenshot, volume and camera. Each event takes an OGG or
WAV file (FLAC, MP3, M4A and Opus are converted with ffmpeg when it is installed on this computer).
Drop a folder: files called `boot`, `login`/`startup`, `logout`, `shutdown`, `error`, `warning`,
`notification`, `usb-in`... are matched to their event. *Play* previews a sound here.

*Apply to the image* writes a freedesktop.org sound theme (`/usr/share/sounds/<id>/`, inheriting
`freedesktop`) and makes it the default: gsettings (GNOME, Budgie, MATE, Cinnamon — only keys that
exist in the image), GTK `settings.ini`, Xfce xsettings and KDE `plasmarc`. Desktops play the event
sounds themselves. Boot and shutdown sounds are played by `eduka-system-sounds.service` (alsa-utils
and vorbis-tools are installed for it), the login sound by an autostart entry (Cinnamon plays its own).
CLI: `distroforge sounds events|themes|show|set|add|clear|apply|remove`.

### 9. Look & Feel → Welcome Screen
Four pages shown after login. Each page has a title, text (**bold**, *italic*, `[links](https://...)`;
an empty line starts a paragraph), an optional picture (left, right, above or below the text), the
logo, alignment, its own background color and up to three buttons: open a website, start a program,
start the installer or close. The window has a title, size, colors and the texts of its buttons.
*Show*: at every login until the user unticks *Show this at startup*, only in the live session, only
on installed systems, or only from the menu. The preview follows the page you edit; *Open the real
welcome screen* runs it on this computer.

In the image it is `/usr/bin/eduka-welcome` (Python + GTK 3; python3-gi and gir1.2-gtk-3.0 are
installed), its design and pictures in `/usr/share/eduka-welcome/`, a menu entry and an autostart
entry. CLI: `distroforge welcome show|export|import|apply|remove`.

### 10. Installer (Calamares)
**Slides** have a title, text (**bold**, *italic*, links), a picture and colors, or are a picture only.
**Check the installer** (also in Check & Build and `distroforge calamares check`): settings.conf
and every module configuration are valid YAML; the branding folder exists and its `componentName` is
the folder name; its images and slideshow exist and the QML is complete; every module of the sequence
is installed and every instance has its configuration; unpackfs copies live-boot's
`/run/live/medium/live/filesystem.squashfs`; the boot loader and its tools fit the Calamares version;
the display manager list matches the image; packages to `remove` are installed (otherwise apt fails
at the end); every file system has its mkfs tool; groups, sudoers group, shell and time zone exist;
commands of shellprocess modules exist. Distro Branding changes the ISO's own branding component and
never renames it, and `bootloaderEntryName` is only changed when `efiBootloaderId` is set.
Edits Debian's installer configuration in `/etc/calamares` while keeping the
comments of the files (only the changed keys are rewritten, and a file is
never written if the result is not valid YAML). Module files that only exist
in `/usr/share/calamares/modules` are copied to `/etc` first.

* **Name, images and colors**: product name and URLs, logo, window icon and
  welcome image (converted to PNG), sidebar colors (Calamares 3.3 and 3.2 key
  spellings), and the name of the desktop launcher (*Install My Linux*).
* **Slideshow**: one image per slide, order and seconds per slide
  (`show.qml`, API 2).
* **Users and passwords**: autologin, root password, reuse password, minimum
  and maximum length, weak passwords, groups, administrator group, shell and
  the computer name template.
* **Live user**: shown here; its name and password (or no password) are set on
  the Users page.
* **Partitions**: preselected option, default and offered file systems, swap
  choices, EFI size, encryption (LUKS1 or LUKS2).
* **Requirements and finish**: minimum disk and RAM, internet and power,
  restart behavior, GRUB timeout, EFI id (keep `debian` for Secure Boot),
  packages removed after installation (*Recommended removals* lists the live
  tools).
* **All configuration files**: browse and edit `/etc/calamares` directly.

Test the installer by booting the ISO in QEMU (Build & Test).

### 11. Advanced → Terminal & Live
* **Live edit session** – starts the image's desktop in a Xephyr window.
  Modes: */etc/skel* (changes become defaults for all users, including the
  live user), *root*, or *sandbox* (temporary, discarded). *Run in session*
  starts any program inside it; *Settings app* opens the desktop's own tools
  (Eduka-Menu settings, LXQt appearance, Xfce/KDE/GNOME settings, ...) to change
  icons, themes, panels and desktop icons visually. When you stop, caches are removed and files
  that mention `/etc/skel` are listed for review.
* **Terminal** – opens your terminal emulator with a root shell inside the
  image (`distroforge shell`); or run one command.
* **Hooks** – scripts in `PROJECT/hooks`, run as root inside the image.
* **Install applications** – type package names (APT), open **Synaptic in a
  window** (installed on request, runs as root in the image), or use the
  terminal. The Build page offers the same right before building.

### 11. Advanced → Package Workshop
Opens an installed package (dpkg-repack style) into `PROJECT/workshop/<pkg>/`:
all its files plus `DEBIAN/control`, `conffiles` and maintainer scripts.
Edit, then *Build and install*: the version becomes `<version>+<id>N`, the
package is installed and (optionally) held with `apt-mark hold`. A copy that
lost files of the original is refused, because dpkg would delete them from
the image. *Restore Debian version* unholds and reinstalls the original.
Prefer Distro Branding for identity changes: it needs no hold, so security
updates keep flowing.

### 12. Review & Apply
Changes chosen in steps 2 to 11 (install a desktop, packages, a theme, the
sounds, the welcome screen, the installer settings, ...) do not change the
image at once: they wait in the Review & Apply list. The green button in the
header shows how many are waiting; closing the window with waiting changes asks
first.

* Tick every change you are sure about. *Go back and change it* opens the step
  of the selected change; *Remove from the list* drops it; *Up*/*Down* change
  the order.
* *Apply all changes* is enabled when every change is ticked. The changes run in
  the list order; when one fails, the ones before it are applied and leave the
  list, the rest keep waiting.
* *Your distribution so far* sums up the name, live user, language, desktop,
  purpose, default applications, sounds, welcome screen and boot loader.

Settings → *Apply every change at once (expert mode)* turns the list off. Things
that only read the image (lists, previews, checks) and the command line always
run at once.

### 13. Check & Build
**Check before building** (also `distroforge check [--deep] [--fix]`):

| Check | Problem when |
|---|---|
| Distribution | not Debian-based, Ubuntu-based or oldstable |
| Build tools | `mksquashfs` or `xorriso` missing on this computer |
| Package database | half-installed packages or an interrupted dpkg run; *Deep check* also runs `apt-get check` |
| Kernel | warning: none in `/boot` or the initrd is missing (the build installs/creates them) |
| Live boot support | warning: live-boot / live-config missing (the build installs them) |
| Desktop | a login screen without any desktop session; the default session is not installed |
| Installer | Calamares without `/etc/calamares/settings.conf` |
| Identity | warning: no name given (the image's own name is used) |
| Edited boot menu | GRUB syntax errors or missing files in your edited boot files |
| Mounts, services | leftover mounts or `/usr/sbin/policy-rc.d` from a crashed task |
| Private data | `machine-id`, SSH host keys (removed by the cleanup) or folders in `/home` |
| Free disk space | less than the expected ISO size + 1 GiB |
| ISO size | information; warning above 4 GiB |

The **How to fix** column says what happens: *Automatic: ...* is fixed by
**Fix automatically** (install missing packages or host tools, `dpkg
--configure -a` and `apt-get -f install`, remove a leftover `policy-rc.d`,
release mounts, correct Calamares settings such as the branding component,
display managers, slideshow or time zone; then the checks run again); *By hand
(double-click)* opens the page that fixes it. *Build ISO image* runs the checks
first; with problems left it asks **Fix automatically**, **I will fix it
myself** or **Build anyway**.

Calamares installs GRUB with `bootloader-config` or its own commands on many
Debian live ISOs (from `grub-*.deb` files in the ISO pool): then a missing
`/usr/sbin/grub-install` in the image is correct and not reported.

**ISO size.** Choose a target: *As small as possible*, 100 MB, 300 MB, 500 MB,
700 MB (CD), 1 GB, 2 GB, 4.4 GB (DVD) or *No limit*. *Estimate* compresses an
evenly spread 16 MiB sample of the system with xz and computes the ISO size of
each method (lz4, zstd 3, zstd 15, zstd 19, xz); the fastest method that
reaches the target is chosen (`build --target-size 500` on the command line).
Squashfs compression is lossless: every file comes back exactly as it was, so a
smaller ISO is never a damaged ISO; it only takes longer to build. When even xz
is too big, the size savers are suggested with what each saves: documentation
(`/usr/share/doc`, copyright and license files stay), manual and info pages,
translations of unused languages, APT lists and old kernels. Removing
applications helps most. The estimate is an estimate: the build log says
whether the target was met.

The build itself then:

1. Checks the system again (Debian-based only).
2. Installs live-boot/live-config and a kernel when missing.
3. Updates the initramfs when packages, Plymouth or hooks changed.
4. Cleans the image (APT cache, logs, history, machine-id, SSH host keys,
   network secrets, temporary files; optional: APT lists, old kernels).
5. Copies kernel and initrd to `/live/vmlinuz` and `/live/initrd.img`,
   removes Debian-Installer entries (Calamares installs your customized
   system; d-i would install plain Debian), applies title/timeout/options.
6. Writes `filesystem.packages` and `filesystem.size`, compresses the root
   filesystem with `mksquashfs` (excludes in `exclude.list`).
7. Writes `sha256sum.txt`/`md5sum.txt`, creates the ISO with `xorriso`
   (replayed or generated boot setup), and `.sha256` (+ `.sha512`, `.md5`).

Boot modes:
* **Replay** – the boot setup of the source ISO (default for extracted ISOs).
  If its boot menu finds the ISO by volume label, the original label is kept.
* **Generate** – new ISOLINUX (BIOS) + GRUB (UEFI) menus and EFI image.
  With `shim-signed` and `grub-efi-amd64-signed` installed the image boots
  with Secure Boot; otherwise an unsigned GRUB is built with
  `grub-mkstandalone`.

Test in QEMU with BIOS, UEFI, or UEFI + Secure Boot (OVMF), with KVM when
available and an optional virtual disk to test installation.

### Keep only the ISO and the project folder
A project is one folder with a sub-folder for each part (README.txt in it explains them): `rootfs/`
(the system, also editable by hand), `iso/` (boot menus and the files around the system), `hooks/`,
`workshop/`, `branding/`, and `boot/`, `cache/`, `logs/`, `output/` made by DistroForge. Check & Build
lists them under *Project folder*.

When the ISO is finished, **Keep only the ISO...** (Check & Build), closing the window after a build,
or `distroforge clean --keep-iso` deletes the project but the ISO images and their checksum files, which
move into the project folder. Everything is unmounted first and nothing is deleted while anything is
still mounted inside the project; only what DistroForge made is deleted, files of your own stay. The
project cannot be opened again afterwards.

### Settings & About → Settings
Global settings (free navigation, apply every change at once, projects folder,
mirror, ...), host tool check with *Install missing packages*, the last errors,
*Save a bug report file* and *Send feedback*.

### Settings & About → About
Version, license (GPL-3.0-or-later), credits, the license of every component
DistroForge uses, trademark notes, the PDF user guide and the donation links (PayPal, Facebook). `distroforge about` prints the same
on the command line. Use a name and logo of your own for your distribution: the
check warns when the name uses a trademark such as Debian or Ubuntu.

## Logs for developers

Every run (GUI and CLI) writes to `/tmp/distroforge/`:

* `distroforge.log` — everything, including every command (rotated at 5 MiB)
* `errors.log` — errors and unhandled exceptions with full tracebacks
* `bug-report-*.tar.gz` — created by Settings → Save a bug report file (logs,
  `project.json`, project logs, versions)
* `outbox/` — feedback reports that wait to be sent; `outbox/sent/` the ones that went out

The project's own log is `PROJECT/logs/distroforge.log`.

## Send feedback

*Send feedback* (sidebar, Settings, and the *Send a report...* button of every error message) opens a
dialog for a bug, an error, an idea, a question or something else: a title, a message, optionally your
e-mail address for an answer, files (screenshots, logs, anything up to 8 MB together, also a screenshot
of the main window) and, if you agree, the logs of DistroForge and the settings of the open project. The
report is packed into one `.tar.gz` and sent over HTTPS through a form-to-mail service to the
developers; nothing else is collected. Without internet it stays in `/tmp/distroforge/outbox/` and is
sent the next time DistroForge starts. `[feedback] url` in the settings file can point it elsewhere.

## Command line

Run `distroforge --help` (the commands in the order of the steps) and
`distroforge COMMAND --help`. The old command `eduka-customizer` still works. See also
`man distroforge`.

## Recipes

A recipe is a JSON file with a list of steps. Paths are relative to the
recipe file. Actions: `sources`, `repo`, `apt-install`, `apt-remove`,
`apt-upgrade`, `deb`, `flatpak`, `desktop`, `session`, `display-manager`,
`eduka-desktop`, `identity`, `locale`, `plymouth`, `wallpaper`, `login`,
`hook`, `command`, `boot`, `branding`, `themes`, `session-type`, `compositor`,
`sddm-theme`, `language`, `users`, `assets`, `calamares`, `kernel`, `boot-file`, `replace-app`, `sounds`, `welcome`, `grub-theme`, `boot-loader`, `build`.
`desktop` takes `"edition": "mini" | "compact" | "full" | "full_apps"`;
`replace-app` takes `role`, `package` and `remove`. `boot-loader` takes `id` (grub, grub-secureboot, systemd-boot, refind, efistub, syslinux) and
optional `settings`, e.g. `{"action": "boot-loader", "id": "syslinux", "settings": {"TIMEOUT": 3}}`. Examples:
`examples/my-distro.json` (Xfce, a general distribution) and
`examples/school-edition.json` (Eduka-Desktop school edition).
`recipe export` writes a recipe from the current project.

## Troubleshooting

* *"Another DistroForge instance is using ..."* – close the other window
  or remove `PROJECT/.lock` if no instance runs.
* *Busy mounts after a crash* – `sudo distroforge -p PROJECT clean --unmount-only`.
* *The ISO stops in an `(initramfs)` shell* – live-boot is missing or the
  initramfs is old: build again with *Initramfs: Always rebuild*.
* *GNOME does not start in the live edit window* – GNOME needs systemd user
  services; test GNOME images in QEMU instead.
* Logs: `PROJECT/logs/distroforge.log`.
