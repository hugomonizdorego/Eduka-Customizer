# Contributing to DistroForge

Thank you for helping DistroForge!

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
eduka_customizer/core/   logic without any GUI code (usable from the CLI and recipes)
eduka_customizer/gui/    PyQt6 interface; pages/ has one file per sidebar page
data/                    desktops.json, exclude.list, config, launchers, polkit, desktop file
tests/                   pytest unit tests (fake root filesystems, no root required)
tools/make_guide.py      writes the PDF user guides in docs/ from docs/screenshots
examples/                recipes and hook scripts
debian/                  Debian packaging (3.0 native)
```

## Rules

* Keep the scope: Debian stable/testing/sid and Debian-based distributions only (never Ubuntu-based).
* New features go into `core/` first (with a test), then get a GUI page or
  card and, when useful, a CLI command and a recipe action.
* Long operations run through `MainWindow.run_task` so the GUI never freezes.
* Never run user-provided strings through a shell on the host; validate
  package names, app IDs, file names and host names (see `core/apt.py`).
* Commit messages: a short summary line, then what and why.
