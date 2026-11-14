# D!sco 0.11.1 — Distro Custom

<img src="icons/hicolor/128x128/apps/disco.png" align="right" width="110" alt="D!sco: a penguin tinkering with a computer">

**D!sco (Distro Custom)** turns a **Debian** or **Devuan** live ISO into **your own Linux distribution**,
step by step: open the ISO, change what you like, press **Finish**. It is made to be easy for beginners and
complete for experts, and it uses Debian's own tools only — `live-boot`, `mksquashfs`, `xorriso`,
`mmdebstrap`/`debootstrap`, `chroot` and Calamares — nothing of Ubuntu (no casper, no PPAs).

The result is a **hybrid live ISO** (BIOS + UEFI, with the Calamares installer) for PCs, or an **SD-card
image** for the Raspberry Pi. ARM64 and RISC-V systems can be made too.

![Welcome](docs/screenshots/01-welcome.png)

**Step-by-step guide (PDF):** [docs/Disco-Guide.pdf](docs/Disco-Guide.pdf) ·
**Same guide as text:** [docs/manual.md](docs/manual.md) · **Quick start:** [docs/QUICKSTART.md](docs/QUICKSTART.md)

**Support the project:** [Donate with PayPal](https://paypal.me/hugocenturion0311) ·
[Facebook](https://facebook.com/hugomonizdorego)

> D!sco is free and open source software (GPL-3.0-or-later). It was called **DistroForge** (0.9 Beta) and
> **Eduka-Customizer** (up to 0.17 Alpha). It is not affiliated with Debian, Devuan or Raspberry Pi Ltd.

## How it works

| Step | What you do there |
|---|---|
| Welcome | What D!sco does, recommendations, support (and *Show this page when D!sco starts*) |
| 1 Start | **Extract an ISO** into a new project, or **continue a project** where you stopped |
| 2 System | Repositories, name of the system, system files (os-release, issue, hostname, motd...), users, language |
| 3 Software | Desktop, popular applications with tick boxes, every Debian package, Flatpak, default apps |
| 4 Startup | What starts by itself: services and programs after login, on or off with a tick |
| 5 Branding | Wallpaper & logo (choose → *Set as default* → *Apply*), login screen, boot splash, a PDF on every desktop |
| 6 Look & Feel | Themes, sounds, welcome screen, bash prompt, browser home page and bookmarks |
| 7 Boot | Kernel, boot loader, boot menu, init system (systemd, SysVinit, OpenRC, runit), Raspberry Pi |
| 8 Installer | Calamares, no installer, or your own .deb packages |
| 9 Files & Terminal | Your folders (no administrator rights needed), the system as administrator, a terminal |
| 10 Review & Apply | The list of your changes, applied all at once |
| 11 Build | **Finish**: checks, then the ISO or SD-card image |

Every step has **Back** and **Next** at the bottom. Your work is saved in the project folder: close D!sco at
any time and continue later from Start.

## Before you start

* **An internet connection** (recommended): installing packages, desktops, Flatpak applications and kernels
  needs it. Extracting and editing work offline; D!sco shows the connection on the Start page.
* Debian 12 or newer (or a Debian-based system), 4 GB of memory, about 20 GB of free disk space.
* An ISO to start from: the small **Debian live standard ISO** (no desktop) is the cleanest start.

```sh
sudo apt install ./disco_0.11.1_all.deb
sudo apt install qemu-user-static binfmt-support    # only to make ARM or RISC-V systems on a PC
```

## Writing the image

```sh
lsblk     # find the USB stick or SD card first, for example /dev/sdb
sudo dd if=mylinux-1.0-stable-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
xzcat mypi-1.0-stable-arm64.img.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
```

> **Warning:** `dd` erases the whole device named in `of=` without asking. Check the name with `lsblk` first.

## What is new in 0.11.1

* **Fixed:** the Builder page of 0.11 crashed when its step buttons were pressed
  (`'int' object is not callable`). The Builder and the Quick Wizard are gone: there is one clear path now.
* **Welcome** page first (about, PayPal donation, *Show this page when D!sco starts*), then **Start**:
  extract an ISO or continue a project, with an internet check.
* **Next / Back / Finish** at the bottom of every step.
* **Startup** step, **Files** page, easy **Wallpaper & Logo**, **Popular applications**.
* New logo: a penguin tinkering with a computer.
* A test presses **every button of every page** (500+) and runs the work behind them; every script was
  checked again (shellcheck, pyflakes, two code reviews).
* Everything in US English (window, guide, screenshots, documents).

## Command line

```sh
sudo disco new --iso debian-live-13.1.0-amd64-standard.iso /home/disco/mylinux
cd /home/disco/mylinux
sudo disco brand identity name="My Linux" version=1.0
sudo disco apt install vlc gimp
sudo disco build --target-size 700
disco --help           # every command
```

## Building from source

```sh
make check                         # compile, lint and tests
dpkg-buildpackage -us -uc -b       # the Debian package
QT_QPA_PLATFORM=offscreen python3 tools/screenshots.py   # the screenshots of the guide
QT_QPA_PLATFORM=offscreen python3 tools/make_guide.py    # docs/Disco-Guide.pdf and docs/manual.md
```

`disco/core` holds everything that changes or builds a system (usable without the window), `disco/gui` the
window (PyQt6, PyQt5 as fallback), `disco/cli.py` the commands, `data/` the catalogs and the scripts that go
into the images, `tests/` the tests.

## License

GPL-3.0-or-later. Menu icons: Papirus (GPL-3.0) and own icons (GPL-3.0-or-later), see
`data/icons/menu/README.md`. Debian is a registered trademark of Software in the Public Interest, Inc.;
Raspberry Pi is a trademark of Raspberry Pi Ltd; Linux® is the registered trademark of Linus Torvalds. The
penguin of the D!sco logo is a friend of Tux, the Linux mascot.
