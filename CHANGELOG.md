# Changelog

## 0.9.0 Beta — 2026-10-08

The first beta on the way to 1.0. The Debian version is `1:0.9.0~beta`: the epoch keeps upgrades from
0.17 Alpha working.

### New
* **Boot loaders of installed systems** (Kernel & Boot → Boot Loader, CLI `boot-loader
  list|show|set|install|remove|use`, recipe `boot-loader` with `settings`): GRUB 2, GRUB 2 with Secure
  Boot, systemd-boot, rEFInd, EFISTUB and Syslinux/EXTLINUX, each with its own settings. GRUB,
  systemd-boot and rEFInd are installed by Calamares' bootloader module; EFISTUB and Syslinux by
  `shellprocess@distroforge-bootloader`, which runs `/usr/sbin/distroforge-bootloader` in the new
  system and adds the settings of systemd-boot and rEFInd. Fallbacks (Syslinux on UEFI → EFISTUB or
  GRUB, EFISTUB on BIOS → Syslinux or GRUB, encrypted or unsupported /boot → GRUB) keep installations
  from failing; kernel and initramfs hooks keep EFISTUB and Syslinux up to date. Removing a boot loader
  never removes the one in use or unrelated packages. Tested with QEMU (SeaBIOS: MBR and GPT; OVMF).
* **Keep only the ISO** after the build (closing the window, Check & Build, `clean --keep-iso`): the
  build folders are deleted, the ISO and its checksums stay; never while something is mounted, never
  files DistroForge did not make. README.txt in every project folder.
* **Send feedback**: bugs, errors, ideas and questions with files, screenshots and (optionally) logs,
  sent over HTTPS to the developers; kept and sent later without internet. Error messages offer it.

### Changed
* 13 steps: System Sounds and Welcome Screen are tabs of Look & Feel; GRUB Design is part of Boot Menu;
  the GRUB settings of installed systems moved from Kernel to Boot Loader; Settings and About share one
  menu. Review & Apply shows the tab of each change.
* New slate and blue colors in light and dark mode.
* One user guide, in English.

### Fixed
* Opening links, the user guide and folders failed with *No such file or directory: 'runuser'* when
  started through pkexec (runuser is in /usr/sbin); every opener now uses full paths and falls back.
* The boot loader table no longer sorts away from its descriptions.

## 0.17.0 Alpha — 2026-10-08

### Changed
* **New name: DistroForge** (was Eduka-Customizer). Package `distroforge`, command `distroforge`,
  settings `/etc/distroforge/distroforge.conf`, data `/usr/share/distroforge`, logs
  `/tmp/distroforge/`. The package replaces `eduka-customizer`; the commands `eduka-customizer` and
  `eduka-customizer-pkexec` and the old settings file keep working. File names inside built images
  stay the same, so older projects build as before.
* **Step 14 Review & Apply**: changes chosen in steps 2–13 wait in one list; tick each, go back and
  change it, remove it or reorder, then apply them all (Settings can switch back to applying at once).
  Check & Build is step 15.
* Clearer texts on every page, in dialogs and in `distroforge --help` (commands listed by step).
* Nothing is preset for one distribution any more: the school example is
  `examples/school-edition.json` with a neutral name.

### New
* **Fix automatically or by hand**: a *How to fix* column in Check & Build and in the installer check;
  *Fix automatically* (`check --fix`) installs missing packages and host tools, repairs dpkg, removes a
  leftover policy-rc.d, releases mounts and corrects Calamares settings, then checks again. Building
  with problems left asks *Fix automatically*, *I will fix it myself* or *Build anyway*.
* **ISO size targets**: smallest, 100 MB, 300 MB, 500 MB, 700 MB, 1 GB, 2 GB, 4.4 GB or none, with an
  estimate from a compressed sample of the system (`build --target-size`). New lossless size savers:
  documentation (license files stay), manual pages, unused translations.
* **About page** and `distroforge about`: license, credits, the license of every component, trademark
  notes, PDF user guides, PayPal and Facebook links; a *Support DistroForge* button in the sidebar.
* **PDF user guides** in Indonesian and English (`docs/DistroForge-Panduan.pdf`,
  `docs/DistroForge-Guide.pdf`, made by `tools/make_guide.py`), installed in
  `/usr/share/distroforge/guide/` (minimal systems drop /usr/share/doc).
* A warning when the distribution name uses a trademark (Debian, Ubuntu, ...).

### Fixed
* *"grub needs /usr/sbin/grub-install in the image"* is no longer reported when Calamares installs GRUB
  itself (bootloader-config, its own commands or grub packages in the ISO pool), as on Debian live ISOs.

## 0.16.0 Alpha — 2026-10-08

### New
* **System Sounds** (step 10): boot, login, logout, shutdown, error, warning, information, question,
  messages, e-mail, complete, bell, devices, power, battery, trash, screenshot, volume and camera
  sounds as a freedesktop sound theme, the default of every desktop (gsettings only for schemas in the
  image, GTK, Xfce, KDE); boot/shutdown sounds via a systemd service, login sound via autostart; files
  matched to events by name; MP3/FLAC converted with ffmpeg. CLI `sounds`, recipe `sounds`.
* **Welcome Screen** (step 11): four designed pages (title, rich text, logo, picture, colors, buttons
  for websites, programs or the installer), a live preview, shown after login until unticked, only
  live, only installed or only from the menu. A small GTK program in the image. CLI `welcome`.
* **Identity & Branding from the ISO**: fields and artwork start from the extracted ISO.
* **Editions in each desktop's words** with the Debian description of the package.
* **Flathub by category** for every kind of distribution (API, otherwise AppStream via flatpak).
* **Kernel terminal** for third-party repositories; repositories stay only with their kernel.
* **Look & Feel per desktop**: themes.json with compatibility; window themes for Xfwm4, Openbox,
  Cinnamon, Marco/Metacity, Plasma global theme and Kvantum.
* **Calamares**: text slides; `calamares_check` (also in Check & Build and `calamares check`).
* **GRUB Design**: third-party GRUB themes checked and refused when incompatible, menu designer,
  boot loader of installed systems (GRUB, GRUB + Secure Boot, systemd-boot, rEFInd). CLI
  `grub-theme`, `boot-loader`.
* **Modern look**: gradient sidebar, pill tabs, cards, *Step N of 14* with a progress bar.

### Changed
* Replace apps applies to everyone (desktop settings and /etc/skel too).
* Distro Branding keeps the ISO's Calamares branding component and EFI id.

### Fixed
* Changing the product name no longer changes `bootloaderEntryName` when the EFI folder depends on it
  (Debian's signed GRUB would not boot).
* Quotes in names no longer break Calamares branding or slides.

## 0.15.0 Alpha — 2026-10-08

### Changed
* **A builder for every Debian-based distribution.** Eduka-Customizer is no
  longer made only for Edukasaun OS: new projects start without a name, ID,
  host name, home page or codename, and every fallback comes from the image's
  own `os-release` (ISO file name, volume label, boot menu title, xorriso
  publisher, branding). The Education purpose recommends Xfce; Eduka-Desktop
  stays in the list of desktops. Configuration files in the image are called
  `*-eduka-customizer*` (old `*-edukasaun*` files are renamed when a project
  is opened). `[edukasaun]` in the settings is now `[eduka_desktop]`.
* **Menus merged into 12 steps** with tabs: Start, Repositories, Identity &
  Branding, Users, Language, Desktop, Software (Packages, Flatpak apps,
  Replace apps), Kernel & Boot, Look & Feel (Themes & Icons, Wallpaper &
  Login, Plymouth), Installer, Advanced (Terminal & Live, Package Workshop),
  Check & Build.
* **Step by step.** A step opens when the one before it is done (*Done — next
  step*, ✔ in the sidebar). Settings → *Free navigation (expert mode)* opens
  every menu; the Quick Wizard opens every step when it finishes; projects
  from older versions keep every step open.

### New
* **Desktop editions**: Mini, Compact, Full and Full with apps for every desktop
  and window manager (GUI, Quick Wizard, `desktop install --edition`, recipes).
* **Debian-only desktop list**: GNOME, KDE Plasma, Xfce, Cinnamon, MATE, LXQt,
  LXDE, Budgie, GNOME Flashback, Enlightenment, Eduka-Desktop; Openbox, i3,
  Fluxbox, IceWM, awesome, JWM, herbstluftwm, bspwm, dwm, spectrwm, Sway, labwc,
  Wayfire, Hyprland. Native compositors Metacity and Enlightenment's added.
* **ISO editions**: Minimal, Full, Full with recommended apps in *What is your
  distribution for?*, the Quick Wizard and `purpose apply --edition`.
* **Replace apps**: replace the default browser, mail, word processor,
  spreadsheet, editor, file manager, terminal, image viewer, video and music
  player, PDF viewer, archive manager or calculator (`data/apps.json`); sets
  `/etc/xdg/mimeapps.list` and `update-alternatives`; CLI `apps`; recipe
  action `replace-app`.
* **Check & Build**: checks before every build (`core/preflight.py`, CLI
  `check [--deep]`, `build --skip-checks`).
* `examples/my-distro.json`: a general Debian-based distribution.

### Fixed
* Removing an application that a metapackage depends on
  (`task-gnome-desktop`, `kde-standard`, ...) no longer lets `autoremove`
  remove the whole desktop: what the metapackage installed is marked manual
  first.

## 0.14.0 Alpha — 2026-10-07

### New
* **What is your distribution for?** When a project gets its system (ISO,
  download, new Debian base) Eduka-Customizer asks: *Education*, *Server*,
  *Professional*, *Home* or *Other*. Each purpose lists recommendations —
  desktop, login screen, session, compositor, icons and theme,
  applications, Flatpak apps, firmware, installer, boot splash — that can be
  unticked one by one, applied, or closed to build everything yourself.
  Also on the Start page, in the Quick Wizard (first step) and on the
  command line (`eduka-customizer purpose list|show|apply`).
* **Package browser**: every package of the image's Debian sources (read
  directly from the APT lists, about 1 second for 75,000 packages), search
  as you type, *Applications / All / Installed / My changes* views and
  sections; tick to install, untick to remove (essential packages are
  protected). *Remove applications of the ISO* lists the programs with a
  menu entry that came with the source ISO. Both are also in the Quick
  Wizard. Installing through a terminal or Synaptic stays available.
* **Your own look by drag and drop**: drop folders, archives (.zip,
  .tar.gz, .tar.xz, .tar.bz2) or files on the Themes & Icons page (or the
  Quick Wizard). GTK themes go to /usr/share/themes, icon and cursor themes
  to /usr/share/icons (with icon cache), fonts to /usr/share/fonts (with
  fc-cache), Plymouth and SDDM themes to theirs, pictures to the wallpaper
  gallery, .deb files are installed. CLI: `eduka-customizer assets`.
* **Wallpaper gallery**: add many wallpapers (drop pictures or folders),
  make one the default (★), remove; all of them are offered in the
  wallpaper choosers of GNOME, Cinnamon and MATE. CLI: `wallpapers`.
* **Native compositors**: Mutter (GNOME), Muffin (Cinnamon), KWin (KDE),
  xfwm4 (Xfce), Marco (MATE) and Budgie's own window manager. Only the
  compositors that fit the desktop are offered; picom is refused for
  desktops that always composite, and its autostart entry is kept out of
  them (NotShowIn), so two compositors never fight. On Wayland, GNOME and
  KDE are their own compositor.
* **Debian derivatives** such as Linux Mint Debian Edition (LMDE) are
  accepted; Ubuntu-based systems (including Ubuntu-based Linux Mint) stay
  refused. The **Debian live standard ISO** (no desktop) is the recommended
  source and is preselected for downloads.
* **Menu icons**: every menu has its own GPL-3.0 icon (Papirus, bundled in
  data/icons/menu). New flat application icon: a monitor with an ISO disc
  and a wrench, in PNG sizes 16-256 and SVG.
* Live user defaults to **live** / **Live**; example names removed.
* The .deb is built without compression and ships the documentation and
  screenshots.

### Fixed
* Setting a wallpaper failed on images without GNOME (missing schema folder).
* KDE on Wayland was offered labwc as compositor.
* Archives with relative links inside (common in icon themes) were refused.
* The Flatpak and Settings pages depended on helpers of the old Packages page.

## 0.13.0 Alpha — 2026-10-07

### New
* **Users** page: the live user with **its own password**, **no password**
  (user name only) or Debian's default `live`; automatic login and groups;
  *Remove* returns to Debian's defaults. Accounts built into the image:
  create with or without a password, as administrator (sudo), change or
  remove the password, delete the account. Also in the Quick Wizard (the
  recipe stores only the password hash), in recipes (`users`) and on the
  command line (`eduka-customizer users`, passwords asked for or read with
  `--password-stdin`).
* Default time zone **Asia/Dili** (Timor-Leste) for new projects, the
  language page, the boot menu language entries and Calamares. Choosing a
  language changes the keyboard, not the time zone.
* The sidebar follows the order of the work, numbered **1. Start / Project**
  to **18. Build & Test**; every step has **Back** and **Next step** buttons.
* US English everywhere: the boot menu submenu is now "Language", and
  "canceled" is spelled the US way (`runner.Cancelled` stays as an alias).

### Fixed
* "Reuse existing filesystem.squashfs" was remembered by the project, so every
  later build silently skipped compressing the system (stale ISO content).
  It now applies to one build only.
* `kernel remove ..` could delete `/lib` of the image: only installed kernel
  versions are accepted.
* `kernel grub KEY=false` wrote `"False"`, which GRUB ignores.
* After one build, renaming the distribution did not change the boot menu
  title or the volume label of later builds.
* Boot options could only be added: removing `toram` or `nomodeset` now
  removes them from the ISO menu too.
* *Rebuild boot files only* / *Apply to the ISO now* refuse when the ISO
  kernel changed or the initramfs must be rebuilt (the compressed system
  would not match).
* Volume-label checks did not read the GRUB files inside `efi.img`.
* Choosing a `.plymouth` file installed another theme from the same folder.
* The Plymouth preview pasted the distribution name unescaped into a root
  shell script.
* `boot/isolinux/*.cfg` was checked as a GRUB file.
* Calamares 3.2 (Debian 12): the EFI size and user shell use the 3.2 keys.
* Empty inputs: kernel install with an empty field, `bootmenu show` without
  a file, `kernel iso`/`third-party` without a name now explain the problem.
* Boot Menu page: "Keep this edit" remembers an edit saved without keeping.
* Live user: after *Remove* the Users page and CLI show Debian's user again.
* Recipes: `comment` keys in a `users` step are ignored instead of failing.

## 0.12.0 Alpha — 2026-10-07

### New
* **Language** page: default language, keyboard layout and variant, time
  zone, translations and spell checking for installed programs (LibreOffice,
  Firefox, Thunderbird, hunspell, CJK fonts and input), a *Language* submenu
  in the GRUB and ISOLINUX menus of the ISO, Calamares defaults. The default
  language can also be chosen when a project is created from an ISO, a
  download or a new Debian base, and in the Quick Wizard.
* **Calamares** page: product name and URLs, logo, icon and welcome images,
  sidebar colors, slideshow, launcher name, user and password rules, live
  user password (SHA-512 hash via live-config), partitioning (file systems,
  swap, EFI size, LUKS1/LUKS2), requirements, restart behavior, GRUB timeout,
  EFI id, packages removed after installation, and an editor for every file
  in /etc/calamares. Comments in the files are kept.
* **Plymouth** page: install themes from .deb, .zip, .tar.*, a folder, a
  .plymouth file or Debian packages; preview them in a window (plymouthd with
  the X11 renderer in Xephyr); apply; remove; create from a logo; delay and
  HiDPI settings.
* **Boot Menu** page: menu settings and direct editing of grub.cfg,
  isolinux.cfg and the GRUB files inside efi.img, with a syntax check, kept
  edits (re-applied at every build) and revert. *Apply to the ISO now* and
  *Rebuild boot files only* rebuild the ISO in seconds.
* **Kernel** page: install Debian, backports, Liquorix, XanMod, own-repository
  or .deb kernels; remove kernels; hold; update initramfs; choose the ISO
  kernel; GRUB defaults of the installed system; firmware; DKMS.
* Install applications with APT, **Synaptic in a window** or a terminal
  (Terminal & Live), also right before building (Build & Test).
* CLI: `language`, `calamares`, `plymouth`, `kernel`, `bootmenu`; recipe
  actions `language`, `calamares`, `kernel`, `boot-file`.
* Ready-made package in `release/`.

### Fixed
* Held packages were not counted as installed.
* Kernel option changes rewrote boot entries that did not change (tabs were
  lost); entries written with tabs were not updated at all.
* Setting a time zone failed in images without tzdata.
* Applying a Plymouth theme failed where plymouth-set-default-theme is missing.
* Live sessions now end when the desktop or program inside them ends.

## 0.11.0 Alpha — 2026-10-07

### New
* **Quick Wizard**: eight steps (source, identity, base system, desktop, look,
  applications, branding, finish) that write a recipe and run it, optionally
  building the ISO. The recipe is saved as `recipe-wizard.json`.
* **Distro Branding Studio**: generates and installs `<id>-branding`, which
  replaces with dpkg diversions the identity of base-files (os-release,
  issue, issue.net), lsb-release (`/etc/lsb-release`), distro-info-data
  (`<id>.csv`), desktop-base (wallpaper, login and GRUB artwork through
  alternatives), the Debian logos (desktop-base, icon themes, Plymouth),
  GRUB of the installed system (`/etc/default/grub.d`), and the Calamares
  installer (branding, slideshow, EFI id). Secure Boot keeps working
  (`EFI/debian` copy, Calamares `efiBootloaderId`). Optional
  `<id>-archive-keyring` with a generated ed25519 signing key. The Debian
  source trees (control, changelog, copyright, rules, install, maintainer
  scripts) are editable in the GUI and rebuilt with one click. No package
  repository is needed; removing the package restores Debian's files.
* **Package Workshop**: open any installed package, edit files, control data
  and maintainer scripts directly, rebuild with a `+<id>N` version, install,
  hold, or restore Debian's version. Refuses to build a copy that lost files
  of the original.
* **Themes & Icons**: GTK/icon/cursor/LXQt theme, font and dark style for all
  major desktops, one-click theme packs (availability checked), theme import,
  desktop icons.
* **Login screens**: LightDM with GTK, Slick, Arctica or KDE greeter, SDDM
  with themes, GDM, LXDM, Ly, greetd + tuigreet, with an availability check.
* **X11 or Wayland** per desktop and **compositor** choice: picom (light,
  shadows, glass blur, off), xcompmgr, built-in, or labwc/KWin/Wayfire/Sway.
* Live session: open the desktop's own settings apps inside the session.
* CLI: `branding`, `workshop`, `themes`, `desktop session-type|compositor|sddm-theme`;
  recipe actions `branding`, `themes`, `session-type`, `compositor`, `sddm-theme`.
* Developer logs in `/tmp/eduka-customizer/` (debug log, error log with
  tracebacks, unhandled-error dialog, bug report archive).
* Installable on Ubuntu and Ubuntu-based systems: PyQt6 or PyQt5,
  Python ≥ 3.9 (tested on Ubuntu 24.04 with its own Python 3.12 + PyQt6 6.6).
* Screenshots of every page in `docs/screenshots/`.

### Fixed
* gpg-agent failed for projects with long paths (socket path limit).
* Installing a rebuilt package could fail after an interrupted dpkg run;
  installs now run `dpkg --configure -a` first and reinstall with dpkg + apt -f.
* Files and directories copied from ISOs or theme archives never read device
  nodes, FIFOs or sockets.
* Dark mode: combo boxes and spin boxes now use a dark palette.
* Debug output no longer floods the log panel (it goes to /tmp instead).

## 0.10.0 Alpha — 2026-10-07

Complete rewrite of Customizer as **Eduka-Customizer**, the ISO builder of
Edukasaun OS. The history of the original project is kept in
[docs/LEGACY-CUSTOMIZER-CHANGELOG](docs/LEGACY-CUSTOMIZER-CHANGELOG).

### Focus
* Only Debian stable, testing, sid and Edukasaun OS. Ubuntu and every
  Ubuntu derivative (casper images, `ID`/`ID_LIKE=ubuntu`) are refused;
  oldstable only when explicitly allowed.
* Debian live layout (`/live`, live-boot, live-config) instead of casper.

### New
* New GUI (PyQt6): sidebar navigation, cards, light/dark theme, live log,
  progress bar, cancellation, one background task at a time.
* Sources: extract ISO (loop mount or xorriso), download official Debian
  live images with SHA256/GPG verification and resume, bootstrap a new base
  with mmdebstrap/debootstrap, snapshot the running system.
* Boot: replay the source ISO's boot setup (copied out of the ISO so it can
  be deleted), or generate ISOLINUX + GRUB EFI, with shim/signed GRUB for
  Secure Boot. Kernel/initrd normalization, Debian-Installer entry removal,
  title/timeout/kernel option editing, boot splash.
* Eduka-Desktop: fetch from git, build `.deb`, install with dependencies,
  edit defaults for new users read from the installed version.
* Desktops: Eduka-Desktop, LXQt, Xfce, KDE, GNOME, MATE, Cinnamon, LXDE,
  Budgie, Openbox, i3, Fluxbox, IceWM, awesome, Sway, labwc; LightDM, SDDM,
  GDM, LXDM; default session; LXQt window manager.
* Flatpak/Flathub: setup, search (API with in-image fallback), curated school
  apps, install now or on first boot.
* APT: deb822 suite presets, third-party repositories with keyrings, file
  editor, search/install/remove/upgrade, local `.deb`, package lists.
* Branding: os-release with dpkg-divert protection, issue, hostname,
  live-config user, locales/time zone/keyboard, Calamares strings,
  Plymouth (choose, import, generate), wallpaper, login screen.
* Live edit session in Xephyr (skel/root/sandbox modes), chroot terminal,
  commands, hooks, boot file editor.
* Build: zstd/xz/gzip/lz4/lzo, clean-up (machine-id, SSH keys, logs, history,
  network secrets, caches), initramfs only when needed, manifests,
  in-ISO checksums, ISO checksums, disk space check.
* QEMU testing: BIOS, UEFI, UEFI + Secure Boot, KVM, test disk.
* CLI with subcommands, JSON recipes, `doctor`, man page, Debian packaging,
  polkit launcher that works on X11 and Wayland, unit tests and CI.

### Fixed (compared to Customizer 4.x)
* The chroot bound the host's `/tmp` and `/var/lib/dbus` into the image; it
  now uses a private `/run`, a slave recursive `/dev` and reference-counted
  mounts that are always cleaned up, even across processes.
* Nested X session race (the session could start before Xephyr was ready).
* `qemu.py` used `sys` without importing it.
* `PURGE_KERNEL` was read as the string "False", which is true in Python, so
  the kernel purge option could not be turned off.
* `os.chmod(hook, stat.S_IEXEC)` removed the read permission, so hook scripts
  could not run.
* ISOs larger than 4 GiB: ISO level 3 is always used.
* Python 2 code paths, the removed `imp` module, `SafeConfigParser` and
  PyQt4 are gone.

### Dependencies
* Python ≥ 3.11, PyQt6 (was Python 2/3 + PyQt4/5).
* `polkitd` + `pkexec` (was `policykit-1`), `qemu-system-x86` + `ovmf`
  (was `qemu-kvm`), `mmdebstrap`, `mtools`, `dosfstools`, `grub-efi-amd64-bin`,
  optional `shim-signed` and `grub-efi-amd64-signed`.
