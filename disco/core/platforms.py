"""Processors and machines D!sco builds for, and what this computer needs for them.

A platform is the machine the distribution runs on: it fixes the Debian
architecture, the kernel, how the computer starts and what D!sco makes:

  iso  a hybrid live ISO (USB stick or DVD) that starts with BIOS and/or UEFI,
       built with mksquashfs and xorriso
  img  an SD-card image for a board (Raspberry Pi), built with sfdisk,
       mkfs.vfat/mtools and mkfs.ext4: flash it with dd or any image writer

Building for another processor than the one of this computer (an ARM image on
an Intel/AMD PC) runs the programs of the image through qemu-user: the kernel's
binfmt_misc hands every ARM program to qemu-aarch64 (or qemu-arm, ...). Only
pure Debian and Devuan tools are used; nothing from Ubuntu (no casper, no PPA).
"""

import os
import platform as _platform
import re
from dataclasses import dataclass, field
from pathlib import Path

from disco.core import runner
from disco.core.log import log

# Debian architecture: (name, qemu-user name, GRUB EFI platform, EFI boot file, GRUB EFI package)
ARCHES = {
    "amd64": ("Intel/AMD 64-bit (x86-64)", "x86_64", "x86_64-efi", "bootx64.efi", "grub-efi-amd64-bin"),
    "i386": ("Intel/AMD 32-bit (x86)", "i386", "i386-efi", "bootia32.efi", "grub-efi-ia32-bin"),
    "arm64": ("ARM 64-bit (AArch64)", "aarch64", "arm64-efi", "bootaa64.efi", "grub-efi-arm64-bin"),
    "armhf": ("ARM 32-bit, ARMv7 (hard-float)", "arm", "arm-efi", "bootarm.efi", "grub-efi-arm-bin"),
    "armel": ("ARM 32-bit, ARMv5/ARMv6 (soft-float)", "arm", "", "", ""),
    "riscv64": ("RISC-V 64-bit", "riscv64", "riscv64-efi", "bootriscv64.efi", "grub-efi-riscv64-bin"),
}
# Debian architectures D!sco does not make images for, and why.
NOT_OFFERED = {
    "ppc64el": "POWER machines start from Petitboot/OPAL: there is no live-boot image route for them in D!sco.",
    "s390x": "IBM Z mainframes are installed with their own tools, not from a live image.",
    "mips64el": "Debian 13 no longer releases mips64el.",
}
# What the host's `uname -m` means as a Debian architecture.
MACHINE_TO_ARCH = {"x86_64": "amd64", "amd64": "amd64", "i386": "i386", "i686": "i386", "aarch64": "arm64",
                   "arm64": "arm64", "armv7l": "armhf", "armv6l": "armel", "riscv64": "riscv64"}
# Architectures a processor runs without emulation.
NATIVE = {"amd64": {"amd64", "i386"}, "arm64": {"arm64"}, "armhf": {"armhf", "armel"}, "i386": {"i386"},
          "riscv64": {"riscv64"}}


@dataclass
class Platform:
    id: str
    name: str
    arch: str
    output: str                      # "iso" or "img"
    description: str
    firmware: str                    # how it starts
    kernel: str                      # Debian kernel package
    packages: list = field(default_factory=list)   # what else the base system needs
    board: str = ""                  # "rpi" for Raspberry Pi
    releases: tuple = ()             # Debian codenames it works with (empty: every supported one)
    experimental: bool = False
    note: str = ""


PLATFORMS = [
    Platform("pc64", "PC, 64-bit (Intel/AMD)", "amd64", "iso",
             "Desktops, laptops and virtual machines from the last 15 years.", "BIOS and UEFI (Secure Boot)",
             "linux-image-amd64"),
    Platform("pc32", "Older PC, 32-bit (Intel/AMD)", "i386", "iso",
             "PCs from before about 2008. Debian 12 (bookworm) is the last release with 32-bit PC kernels.",
             "BIOS", "linux-image-686-pae", releases=("bookworm",),
             note="Debian 13 dropped the 32-bit PC kernel and installer: use Debian 12 (bookworm)."),
    Platform("arm64-efi", "ARM 64-bit with UEFI", "arm64", "iso",
             "Virtual machines, ARM servers and boards that start with UEFI (EDK2/U-Boot UEFI).", "UEFI",
             "linux-image-arm64", ["grub-efi-arm64-bin"]),
    Platform("rpi-arm64", "Raspberry Pi 3, 4 and 400 (64-bit)", "arm64", "img",
             "SD-card image with Debian's own Raspberry Pi firmware package (raspi-firmware).",
             "Raspberry Pi firmware (config.txt, cmdline.txt)", "linux-image-arm64",
             ["raspi-firmware", "firmware-brcm80211", "wireless-regdb", "fdisk", "e2fsprogs", "dosfstools"],
             board="rpi"),
    Platform("rpi5", "Raspberry Pi 5 (64-bit)", "arm64", "img",
             "SD-card image for the Raspberry Pi 5. Debian's kernel supports it from Debian 13 on, still with "
             "gaps (some devices of the board are not supported yet).",
             "Raspberry Pi firmware (config.txt, cmdline.txt)", "linux-image-arm64",
             ["raspi-firmware", "firmware-brcm80211", "wireless-regdb", "fdisk", "e2fsprogs", "dosfstools"],
             board="rpi", experimental=True, releases=("trixie", "forky", "sid")),
    Platform("rpi-armhf", "Raspberry Pi 2 and 3 (32-bit)", "armhf", "img",
             "SD-card image for the Raspberry Pi 2 (and the 3 in 32-bit mode).",
             "Raspberry Pi firmware (config.txt, cmdline.txt)", "linux-image-armmp",
             ["raspi-firmware", "firmware-brcm80211", "wireless-regdb", "fdisk", "e2fsprogs", "dosfstools"],
             board="rpi"),
    Platform("rpi-armel", "Raspberry Pi 1, Zero and Zero W (32-bit)", "armel", "img",
             "SD-card image for the first Raspberry Pi models (ARMv6). Debian 13 is the last release with armel.",
             "Raspberry Pi firmware (config.txt, cmdline.txt)", "linux-image-rpi",
             ["raspi-firmware", "firmware-brcm80211", "wireless-regdb", "fdisk", "e2fsprogs", "dosfstools"],
             board="rpi", releases=("bookworm", "trixie")),
    Platform("riscv64-efi", "RISC-V 64-bit with UEFI", "riscv64", "iso",
             "Virtual machines and RISC-V boards with UEFI (U-Boot). Debian 13 is the first release with "
             "official RISC-V support.", "UEFI", "linux-image-riscv64", ["grub-efi-riscv64-bin"],
             experimental=True, releases=("trixie", "forky", "sid")),
]
BY_ID = {p.id: p for p in PLATFORMS}


def get(platform_id):
    if platform_id not in BY_ID:
        raise KeyError("Unknown platform: {} (use {})".format(platform_id, ", ".join(BY_ID)))
    return BY_ID[platform_id]


def for_arch(arch, output=None):
    """The default platform of a Debian architecture (and output)."""
    for p in PLATFORMS:
        if p.arch == arch and (output is None or p.output == output) and not p.experimental:
            return p
    for p in PLATFORMS:
        if p.arch == arch:
            return p
    return BY_ID["pc64"]


def of_project(project):
    """The platform a project builds for (stored by the Builder, else from the image's architecture)."""
    pid = project.state.get("builder", {}).get("platform")
    if pid in BY_ID:
        return BY_ID[pid]
    arch = project.state.get("distro", {}).get("arch") or "amd64"
    return for_arch(arch, "iso")


def kernel_package(arch, platform_id=None):
    if platform_id in BY_ID:
        return BY_ID[platform_id].kernel
    return for_arch(arch).kernel


def release_ok(p, codename):
    """(True, "") or (False, why) for building *p* from a Debian codename (Devuan names are mapped)."""
    from disco.core.distro import DEVUAN
    code = DEVUAN.get(codename, codename)
    if p.releases and code not in p.releases:
        return False, "{} needs Debian {}".format(p.name, " or ".join(p.releases))
    return True, ""


# This computer ------------------------------------------------------------------------------
def host_arch():
    try:
        out = runner.output(["dpkg", "--print-architecture"], quiet=True, check=False)
        if out.strip():
            return out.strip()
    except (OSError, runner.CommandError):
        pass
    return MACHINE_TO_ARCH.get(_platform.machine(), _platform.machine())


def is_foreign(arch):
    return arch not in NATIVE.get(host_arch(), {host_arch()})


BINFMT = Path("/proc/sys/fs/binfmt_misc")


def binfmt_entry(arch):
    """The binfmt_misc entry that runs *arch* programs, or None."""
    qname = ARCHES.get(arch, ("", arch))[1]
    for name in ("qemu-" + qname, "qemu-" + qname + "-static"):
        p = BINFMT / name
        if p.exists():
            return p
    return None


def can_run(arch):
    """True when programs of *arch* run on this computer (natively or through qemu-user with the F flag,
    which chroot needs because the interpreter is not inside the image)."""
    if not is_foreign(arch):
        return True
    entry = binfmt_entry(arch)
    if not entry:
        return False
    try:
        text = entry.read_text()
    except OSError:
        return False
    flags = re.search(r"(?m)^flags:\s*(\S*)", text)
    return text.startswith("enabled") and bool(flags and "F" in flags.group(1))


def enable_binfmt(arch):
    """Register qemu-user for *arch* in binfmt_misc. Returns (True, how) or (False, what to install)."""
    if can_run(arch):
        return True, "already enabled"
    qname = ARCHES.get(arch, ("", arch))[1]
    if not BINFMT.joinpath("register").exists():
        runner.run(["mount", "-t", "binfmt_misc", "binfmt_misc", str(BINFMT)], check=False, quiet=True)
    if runner.which("update-binfmts"):
        for name in ("qemu-" + qname, "qemu-" + qname + "-static"):
            runner.run(["update-binfmts", "--enable", name], check=False, quiet=True)
            if can_run(arch):
                return True, "update-binfmts"
    for conf_dir in ("/usr/lib/binfmt.d", "/etc/binfmt.d", "/run/binfmt.d"):
        for name in ("qemu-{}.conf".format(qname), "qemu-{}-static.conf".format(qname)):
            conf = Path(conf_dir, name)
            if conf.is_file():
                line = next((l for l in conf.read_text().splitlines() if l.startswith(":")), "")
                if line:
                    try:
                        if binfmt_entry(arch):
                            binfmt_entry(arch).write_text("-1")  # registered without F: register it again
                        BINFMT.joinpath("register").write_text(line)
                    except OSError as e:
                        log.debug("binfmt registration failed: %s", e)
                    if can_run(arch):
                        return True, str(conf)
    if runner.which("systemctl"):
        runner.run(["systemctl", "restart", "systemd-binfmt"], check=False, quiet=True)
        if can_run(arch):
            return True, "systemd-binfmt"
    return False, ("Programs for {} cannot run on this computer. Install qemu-user-static (Debian 12) or "
                   "qemu-user-binfmt (Debian 13) and binfmt-support, then press Prepare again.".format(arch))


def host_requirements(p, method="debootstrap"):
    """[(tool, package, needed for)] that are missing on this computer for building *p*."""
    need = []
    if method == "live-build":
        need.append(("lb", "live-build", "the live-build route"))
    else:
        need.append(("mmdebstrap", "mmdebstrap", "a new base system (or debootstrap)"))
    if p.output == "iso":
        need += [("mksquashfs", "squashfs-tools", "compressing the system"), ("xorriso", "xorriso", "the ISO"),
                 ("mcopy", "mtools", "the UEFI boot image"), ("mkfs.vfat", "dosfstools", "the UEFI boot image"),
                 ("grub-mkstandalone", "grub-common", "the UEFI boot loader of the ISO")]
        if p.arch in ("amd64", "i386"):
            need += [("/usr/lib/ISOLINUX/isolinux.bin", "isolinux", "starting on BIOS computers"),
                     ("/usr/lib/syslinux/modules/bios/vesamenu.c32", "syslinux-common", "the BIOS boot menu")]
    else:
        need += [("sfdisk", "fdisk", "the partition table"), ("mkfs.vfat", "dosfstools", "the boot partition"),
                 ("mcopy", "mtools", "filling the boot partition"), ("mkfs.ext4", "e2fsprogs", "the system partition")]
    if is_foreign(p.arch):
        need.append(("qemu-{}-static".format(ARCHES[p.arch][1]), "qemu-user-static",
                     "running {} programs on this {} computer".format(p.arch, host_arch())))
    missing = []
    for tool, package, why in need:
        if tool == "mmdebstrap" and (runner.which("mmdebstrap") or runner.which("debootstrap")):
            continue
        if tool.startswith("/"):
            if not os.path.exists(tool) and not os.path.exists(tool.replace("/usr/lib/ISOLINUX/", "/usr/lib/syslinux/")):
                missing.append((tool, package, why))
        elif tool.startswith("qemu-"):
            if not (runner.which(tool) or runner.which(tool.replace("-static", "")) or can_run(p.arch)):
                missing.append((tool, package, why))
        elif not runner.which(tool):
            missing.append((tool, package, why))
    return missing


def describe(p):
    """One line about a platform for lists."""
    return "{} — {} ({}, {})".format(p.name, ARCHES[p.arch][0], p.output.upper(), p.firmware)
