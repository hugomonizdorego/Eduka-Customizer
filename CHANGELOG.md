# Changelog

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
