# Roadmap

Status: **D!sco 0.11.1** (November 2026). Version numbers started again with the name D!sco (Distro
Custom); before it was DistroForge (0.9 Beta) and Eduka-Customizer (up to 0.17 Alpha).

## Done in 0.11.1
- One clear path: **Welcome** (about, support, show at start) → **Start** (extract an ISO or continue a
  project, internet check) → eleven steps with **Back / Next / Finish**. The Builder page and the Quick
  Wizard were removed: they were confusing next to the steps.
- **Startup** step: services and programs after login, switched on or off with a tick.
- **Files** page: your folders belong to you (no administrator rights needed); the system is edited as
  administrator in D!sco.
- **Wallpaper & Logo**: choose a picture, *Set as default*, *Apply* — also for the logo, login screen,
  boot menu and picture of new users.
- **Popular applications** with tick boxes on the Packages page.
- New logo: a penguin tinkering with a computer.
- A test that presses every button of every page and runs the work behind it.
- Everything in US English.

## Done in 0.11
ARM64, Raspberry Pi (1/Zero to 5) and RISC-V through qemu-user; SD-card images laid out like Debian's;
UEFI ISOs for ARM64 and RISC-V; the live-build route; system files, terminal and browser branding; a PDF on
every desktop; the installer choice; about 50 fixes from a full code review.

## Next (0.12)
1. **Tests on real hardware**: Raspberry Pi 3/4/400 and 5 with images from real Debian mirrors, ARM64
   UEFI machines, and full Calamares installations in QEMU (BIOS and UEFI, ext4 and btrfs, encryption).
2. **Translations of the window** (Indonesian, Tetum, Portuguese) with Qt Linguist; the texts are ready.
3. **Undo**: snapshots of the system (overlayfs or btrfs) so every change can be taken back.
4. **Builds without root** (mmdebstrap --mode=unshare) for continuous integration.
5. **A signed APT repository** for the branding packages (reprepro/aptly), so they update online.

## Things to watch
- Debian codenames change with every release (now: stable `trixie`, testing `forky`): Settings or
  `/etc/disco/disco.conf`.
- Debian makes no live ISO for sid: start from testing and switch the repositories, or make a new sid system.
- The Raspberry Pi 5 kernel in Debian is still experimental.
