# Contributing to D!sco

Thank you for helping D!sco (Distro Custom)!

## Development setup

```sh
sudo apt install python3-pyqt6 python3-pytest pyflakes3 xorriso squashfs-tools mtools \
    dosfstools isolinux syslinux-common grub-efi-amd64-bin debhelper
make check      # compile + pyflakes
make test       # unit tests (no root needed)
sudo make run   # start the GUI from the source tree
make deb        # build the Debian package
```

## Layout

```
disco/core/              logic without any GUI code (usable from the CLI and recipes)
disco/gui/               PyQt6 interface; pages/ has one file per page (tab)
data/                    catalogs, presets, board and boot loader scripts, config, launchers, polkit
tests/                   pytest unit tests (fake root filesystems, no root required)
tools/screenshots.py     takes docs/screenshots from a demo project
tools/make_guide.py      writes docs/Disco-Guide.pdf and docs/manual.md
examples/                recipes and hook scripts
debian/                  Debian packaging (3.0 native)
```

## Rules

* Keep the scope: Debian (stable/testing/sid) and Devuan, Debian's own tools only (never Ubuntu parts).
* New features go into `core/` first (with a test), then get a GUI page or
  card and, when useful, a CLI command and a recipe action.
* Long operations run through `MainWindow.run_task` so the GUI never freezes.
* Never run user-provided strings through a shell on the host; validate
  package names, app IDs, file names and host names (see `core/apt.py`).
* Commit messages: a short summary line, then what and why.
