# Eduka-Customizer manual

Version 0.14 Alpha.

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
logs/          eduka-customizer.log, live-session.log, qemu.log
```

Only one Eduka-Customizer instance can use a project at a time.

**Supported systems.** Images: Debian stable, testing and sid, Edukasaun OS and
Debian derivatives such as LMDE (Ubuntu-based systems are refused). Recommended
source: the Debian live *standard* ISO (no desktop).
Build computer: Debian, Edukasaun OS, Ubuntu or an Ubuntu-based system.
The check reads `/etc/os-release`, `/etc/debian_version` and the APT sources
of the image. Ubuntu and every Ubuntu derivative are refused, and so are
other Debian derivatives. Debian oldstable is refused unless
`allow_oldstable = yes` is set. Debian codenames live in
`/etc/eduka-customizer/eduka-customizer.conf` (or the Settings page): update
them when Debian makes a new release.

**Chroot.** Commands run inside the image with `chroot`. Eduka-Customizer
mounts `/proc`, `/sys`, `/dev` (recursive bind, made a *slave* so nothing
propagates back to your computer) and a private `/run`, copies your DNS
settings, and blocks services from starting (`policy-rc.d`). Mounts are
shared between the GUI, terminals and the CLI and are removed when the last
user leaves. *Terminal & Live → Unmount everything* or
`eduka-customizer clean --unmount-only` recovers after a crash.

## Pages of the GUI

The sidebar lists the pages in the order of the work, from the source of
the image to the finished ISO. Every page has **Back** and **Next step**
buttons; the Quick Wizard does all steps at once.

### 1. Start / Project
Create or open a project, then pick the source:

* **Edukasaun / Debian ISO** – any `debian-live-*.iso` or Edukasaun OS ISO.
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
| Education | Eduka-Desktop, LightDM, picom (light), Papirus + Arc, LibreOffice, Firefox, GCompris, KGeography, Kalzium, Stellarium, Tux Paint, TuxMath, Marble, KTurtle, Orca, Onboard, VLC; GeoGebra (Flatpak) |
| Server | no desktop; OpenSSH server, ufw, fail2ban, unattended-upgrades, htop, curl, rsync, vim, tmux |
| Professional | KDE Plasma (Wayland) with KWin, SDDM, Breeze, LibreOffice, Thunderbird, Okular, GIMP, Inkscape, Krita, VLC, Remmina, KeePassXC, git |
| Home | Cinnamon with Muffin, LightDM Slick greeter, Papirus + Arc, Firefox, Thunderbird, LibreOffice, VLC, Rhythmbox, Shotwell, Transmission, games |
| Other | nothing: build it yourself |

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
`eduka-customizer recipe apply`.

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

### 3. Identity
* os-release: `NAME`, `PRETTY_NAME`, `VERSION`, `ID=edukasaun`,
  `ID_LIKE=debian`. `VERSION_CODENAME` stays the Debian codename because APT
  tooling uses it; your codename is stored as `EDUKASAUN_CODENAME`.
  `/usr/lib/os-release` is protected with `dpkg-divert` so `base-files`
  upgrades do not undo it.
* `/etc/issue`, `/etc/issue.net`, `/etc/lsb-release`, `/etc/hostname`, `/etc/hosts`.
* Computer name (`/etc/hostname`, `/etc/hosts` and the live session). The live
  user and passwords are on the Users page.
* Calamares branding (`/etc/calamares/branding/*/branding.desc`).

### 4. Users
* **Live user** – the account that logs in when the ISO starts. live-config
  creates it at every boot; Debian's default is `user` with the password
  `live`. Choose the user name, full name, groups, automatic login and the
  password: Debian's default, **your own password** (stored as a SHA-512
  hash in a live-config script) or **no password at all** (`passwd -d`, the
  user logs in without a password). *Remove* returns to Debian's defaults.
  Files: `/etc/live/config.conf.d/50-edukasaun.conf` and
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
  live-config too (`/etc/live/config.conf.d/40-edukasaun-locale.conf`).
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

### 6. Packages
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

### 7. Flatpak apps
*Enable Flatpak + Flathub* installs `flatpak` (and the Discover/GNOME
Software plugin when present) and adds Flathub system-wide. Apps can be
installed into the image now, or listed for installation on the **first boot
of the installed system** (a systemd unit that waits for the network and
skips the live session). The second option keeps the ISO small.

### 8. Kernel
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
* **GRUB of the installed system**: timeout, menu style, default entry,
  kernel options, os-prober, recovery entries and resolution, written to
  `/etc/default/grub.d/95-eduka-customizer.cfg`. Calamares installs GRUB and
  runs `update-grub` with these settings; *Run update-grub* only works in an
  image that already has an installed GRUB menu.
* **Drivers**: install common firmware (needs `non-free-firmware`) and
  rebuild DKMS modules for every kernel.

### 9. Desktop
* Install one of the desktops or window managers from
  `/usr/share/eduka-customizer/desktops.json` (edit it to add more). Debian
  `task-*-desktop` packages are used where they exist; *Remove other Debian
  desktop tasks* purges the others.
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

### 10. Themes & Icons
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

### 11. Wallpaper & Login
* **Wallpaper gallery** in `/usr/share/backgrounds/<id>/`: drop pictures or
  folders, *Make default ★* (applied to every desktop), *Remove*. All
  pictures are listed for the wallpaper choosers of GNOME, Cinnamon and
  MATE (`*-background-properties/<id>.xml`).

* The default wallpaper is set for LXQt/Eduka-Desktop (pcmanfm-qt), Xfce, KDE Plasma, GNOME,
  Cinnamon, MATE and Debian's `desktop-background` alternative.
* Login screen: background, logo, GTK and icon theme for LightDM greeters,
  SDDM theme and background, GDM logo, LXDM background.

### 12. Plymouth
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

### 13. Distro Branding
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

### 14. Calamares
Edits Debian's installer configuration in `/etc/calamares` while keeping the
comments of the files (only the changed keys are rewritten, and a file is
never written if the result is not valid YAML). Module files that only exist
in `/usr/share/calamares/modules` are copied to `/etc` first.

* **Name, images and colors**: product name and URLs, logo, window icon and
  welcome image (converted to PNG), sidebar colors (Calamares 3.3 and 3.2 key
  spellings), and the name of the desktop launcher (*Install Edukasaun OS*).
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

### 15. Boot Menu
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
  Build & Test, `eduka-customizer bootmenu apply`).

### 16. Package Workshop
Opens an installed package (dpkg-repack style) into `PROJECT/workshop/<pkg>/`:
all its files plus `DEBIAN/control`, `conffiles` and maintainer scripts.
Edit, then *Build and install*: the version becomes `<version>+<id>N`, the
package is installed and (optionally) held with `apt-mark hold`. A copy that
lost files of the original is refused, because dpkg would delete them from
the image. *Restore Debian version* unholds and reinstalls the original.
Prefer Distro Branding for identity changes: it needs no hold, so security
updates keep flowing.

### 17. Terminal & Live
* **Live edit session** – starts the image's desktop in a Xephyr window.
  Modes: */etc/skel* (changes become defaults for all users, including the
  live user), *root*, or *sandbox* (temporary, discarded). *Run in session*
  starts any program inside it; *Settings app* opens the desktop's own tools
  (Eduka-Menu settings, LXQt appearance, Xfce/KDE/GNOME settings, ...) to change
  icons, themes, panels and desktop icons visually. When you stop, caches are removed and files
  that mention `/etc/skel` are listed for review.
* **Terminal** – opens your terminal emulator with a root shell inside the
  image (`eduka-customizer shell`); or run one command.
* **Hooks** – scripts in `PROJECT/hooks`, run as root inside the image.
* **Install applications** – type package names (APT), open **Synaptic in a
  window** (installed on request, runs as root in the image), or use the
  terminal. The Build page offers the same right before building.

### 18. Build & Test
1. Checks the system again (Debian/Edukasaun only).
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

### Settings
Global settings, host tool check with *Install missing packages*, the last
errors, *Create bug report*, About.

## Logs for developers

Every run (GUI and CLI) writes to `/tmp/eduka-customizer/`:

* `eduka-customizer.log` — everything, including every command (rotated at 5 MiB)
* `errors.log` — errors and unhandled exceptions with full tracebacks
* `bug-report-*.tar.gz` — created by Settings → Create bug report (logs,
  `project.json`, project logs, versions)

The project's own log is `PROJECT/logs/eduka-customizer.log`.

## Command line

Run `eduka-customizer --help` and `eduka-customizer COMMAND --help`. See also
`man eduka-customizer`.

## Recipes

A recipe is a JSON file with a list of steps. Paths are relative to the
recipe file. Actions: `sources`, `repo`, `apt-install`, `apt-remove`,
`apt-upgrade`, `deb`, `flatpak`, `desktop`, `session`, `display-manager`,
`eduka-desktop`, `identity`, `locale`, `plymouth`, `wallpaper`, `login`,
`hook`, `command`, `boot`, `branding`, `themes`, `session-type`, `compositor`,
`sddm-theme`, `language`, `users`, `assets`, `calamares`, `kernel`, `boot-file`, `build`. Example: `examples/edukasaun-school.json`.
`recipe export` writes a recipe from the current project.

## Troubleshooting

* *"Another Eduka-Customizer instance is using ..."* – close the other window
  or remove `PROJECT/.lock` if no instance runs.
* *Busy mounts after a crash* – `sudo eduka-customizer -p PROJECT clean --unmount-only`.
* *The ISO stops in an `(initramfs)` shell* – live-boot is missing or the
  initramfs is old: build again with *Initramfs: Always rebuild*.
* *GNOME does not start in the live edit window* – GNOME needs systemd user
  services; test GNOME images in QEMU instead.
* Logs: `PROJECT/logs/eduka-customizer.log`.
