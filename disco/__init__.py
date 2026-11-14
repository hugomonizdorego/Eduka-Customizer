"""D!sco (Distro Custom) - build your own Debian-based distribution.

D!sco builds bootable live ISO images (PC and ARM64 UEFI) and SD-card
images (Raspberry Pi) of your own distribution from pure Debian or Devuan:
debootstrap or mmdebstrap, chroot, live-boot and live-config, mksquashfs and
xorriso, or live-build. It can also remaster an existing Debian-based live
ISO. Ubuntu and its ecosystem (casper, PPAs, Ubuntu bases) are intentionally
not supported.
"""

__all__ = ["APP_NAME", "APP_FULL_NAME", "APP_ID", "VERSION", "VERSION_LABEL", "COMMAND"]

APP_NAME = "D!sco"
APP_FULL_NAME = "D!sco (Distro Custom)"
APP_TAGLINE = "Distro Custom: build your own Debian-based distribution"
APP_ID = "io.github.hugomonizdorego.Disco"
COMMAND = "disco"
# Earlier names of this program, newest first.
OLD_NAMES = [("DistroForge", "0.9 Beta to 0.9.5 Beta"), ("Eduka-Customizer", "up to 0.17 Alpha")]
OLD_NAME = OLD_NAMES[0][0]
# D!sco starts its own numbering: 0.11 is the release of November 2026.
VERSION = "0.11"
VERSION_LABEL = "0.11"
HOMEPAGE = "https://github.com/hugomonizdorego/Eduka-Customizer"
DONATE_URL = "https://paypal.me/hugocenturion0311"
FACEBOOK_URL = "https://facebook.com/hugomonizdorego"
AUTHOR = "Hugo Moniz do Rego"
LICENSE = "GPL-3.0-or-later"
