# Eduka-Customizer manual

Version 0.10 Alpha.

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

**Supported systems.** Debian stable, testing and sid, and Edukasaun OS.
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

### Start / Project
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

### Identity & Language
* os-release: `NAME`, `PRETTY_NAME`, `VERSION`, `ID=edukasaun`,
  `ID_LIKE=debian`. `VERSION_CODENAME` stays the Debian codename because APT
  tooling uses it; your codename is stored as `EDUKASAUN_CODENAME`.
  `/usr/lib/os-release` is protected with `dpkg-divert` so `base-files`
  upgrades do not undo it.
* `/etc/issue`, `/etc/issue.net`, `/etc/lsb-release`, `/etc/hostname`, `/etc/hosts`.
* Live user name and host name (`/etc/live/config.conf.d/50-edukasaun.conf`).
* Calamares branding (`/etc/calamares/branding/*/branding.desc`).
* Locales (generated with `locale-gen`), time zone, keyboard; also passed to
  live-config.

### Repositories
* Suite presets write `/etc/apt/sources.list.d/debian.sources` (deb822)
  with `main contrib non-free non-free-firmware`, updates, security and
  optionally backports and `deb-src`. Old Debian entries are kept as
  `*.eduka-old`.
* Moving to a newer suite: apply, then *Packages → Upgrade all*. Moving back
  to an older suite is not supported by APT.
* *Add repository* stores the key under `/etc/apt/keyrings/NAME.gpg` and
  references it with `Signed-By`.
* Every `.list`/`.sources` file can be edited directly.

### Packages
Search (`apt-cache search`), queue packages to install/remove, apply, full
upgrade, autoremove, install local `.deb` files (dependencies are resolved by
APT), import/export package lists (`name` installs, `-name` removes).

### Flatpak apps
*Enable Flatpak + Flathub* installs `flatpak` (and the Discover/GNOME
Software plugin when present) and adds Flathub system-wide. Apps can be
installed into the image now, or listed for installation on the **first boot
of the installed system** (a systemd unit that waits for the network and
skips the live session). The second option keeps the ISO small.

### Desktop
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
* Login manager: LightDM (GTK or Slick greeter), SDDM, GDM, LXDM. Default
  session for the login manager, live autologin and `x-session-manager`.
  Window manager used by LXQt/Eduka-Desktop.

### Appearance
* Plymouth: choose an installed theme, import a theme folder or archive, or
  generate a simple theme from a PNG logo and two colors. The initramfs is
  rebuilt on the next build.
* Wallpaper: LXQt/Eduka-Desktop (pcmanfm-qt), Xfce, KDE Plasma, GNOME,
  Cinnamon, MATE and Debian's `desktop-background` alternative.
* Login screen: background, logo, GTK and icon theme for LightDM greeters,
  SDDM theme and background, GDM logo, LXDM background.
* ISO boot menu: title, timeout, kernel options (e.g. `quiet splash`,
  `toram`, `locales=pt_PT.UTF-8`), kernel version and background image.

### Terminal & Live
* **Live edit session** – starts the image's desktop in a Xephyr window.
  Modes: */etc/skel* (changes become defaults for all users, including the
  live user), *root*, or *sandbox* (temporary, discarded). *Run in session*
  starts any program inside it. When you stop, caches are removed and files
  that mention `/etc/skel` are listed for review.
* **Terminal** – opens your terminal emulator with a root shell inside the
  image (`eduka-customizer shell`); or run one command.
* **Hooks** – scripts in `PROJECT/hooks`, run as root inside the image.
* **Boot files** – edit `grub.cfg` and ISOLINUX files of the ISO directly.

### Build & Test
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
Global settings, host tool check with *Install missing packages*, About.

## Command line

Run `eduka-customizer --help` and `eduka-customizer COMMAND --help`. See also
`man eduka-customizer`.

## Recipes

A recipe is a JSON file with a list of steps. Paths are relative to the
recipe file. Actions: `sources`, `repo`, `apt-install`, `apt-remove`,
`apt-upgrade`, `deb`, `flatpak`, `desktop`, `session`, `display-manager`,
`eduka-desktop`, `identity`, `locale`, `plymouth`, `wallpaper`, `login`,
`hook`, `command`, `boot`, `build`. Example: `examples/edukasaun-school.json`.
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
