"""Check the host computer for the tools Eduka-Customizer uses."""

import os
from pathlib import Path

from eduka_customizer.core import distro, runner

# (tool or file, Debian package, required?, purpose)
CHECKS = [
    ("xorriso", "xorriso", True, "read and write ISO images"),
    ("mksquashfs", "squashfs-tools", True, "compress the root filesystem"),
    ("unsquashfs", "squashfs-tools", True, "unpack the root filesystem"),
    ("chroot", "coreutils", True, "run commands inside the image"),
    ("mount", "mount", True, "mount pseudo filesystems"),
    ("dpkg-deb", "dpkg", True, "build the Eduka-Desktop package"),
    ("git", "git", True, "fetch Eduka-Desktop"),
    ("rsync", "rsync", False, "snapshot the running system"),
    ("mmdebstrap", "mmdebstrap", False, "bootstrap a new Debian base"),
    ("debootstrap", "debootstrap", False, "bootstrap fallback"),
    ("mkfs.vfat", "dosfstools", False, "create the UEFI boot image"),
    ("mcopy", "mtools", False, "fill the UEFI boot image"),
    ("grub-mkstandalone", "grub-common", False, "unsigned UEFI boot loader"),
    ("/usr/lib/grub/x86_64-efi", "grub-efi-amd64-bin", False, "UEFI GRUB modules"),
    ("/usr/lib/shim/shimx64.efi.signed", "shim-signed", False, "Secure Boot"),
    ("/usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed", "grub-efi-amd64-signed", False, "Secure Boot"),
    ("/usr/lib/ISOLINUX/isolinux.bin", "isolinux", False, "legacy BIOS boot"),
    ("/usr/lib/syslinux/modules/bios/vesamenu.c32", "syslinux-common", False, "BIOS boot menu"),
    ("Xephyr", "xserver-xephyr", False, "live edit session"),
    ("qemu-system-x86_64", "qemu-system-x86", False, "test the ISO"),
    ("qemu-img", "qemu-utils", False, "virtual test disk"),
    ("/usr/share/OVMF/OVMF_CODE_4M.fd", "ovmf", False, "UEFI testing"),
    ("gpgv", "gpgv", False, "verify Debian downloads"),
    ("gpg", "gpg", False, "import repository keys"),
    ("pkexec", "pkexec", False, "start the GUI as administrator"),
]


def check():
    results = []
    for item, package, required, purpose in CHECKS:
        ok = Path(item).exists() if item.startswith("/") else bool(runner.which(item))
        results.append({"item": item, "package": package, "required": required,
                        "purpose": purpose, "ok": ok})
    return results


def missing_packages(results=None, required_only=False):
    results = results or check()
    pkgs = []
    have = {r["item"] for r in results if r["ok"]}
    for r in results:
        if r["item"] == "debootstrap" and "mmdebstrap" in have:
            continue
        if not r["ok"] and (r["required"] or not required_only) and r["package"] not in pkgs:
            pkgs.append(r["package"])
    return pkgs


def host_info():
    info = distro.detect("/")
    try:
        distro.validate(info, "/")
        supported = True
        reason = ""
    except distro.UnsupportedDistro as e:
        supported = False
        reason = str(e)
    return {"distro": info, "supported": supported, "reason": reason,
            "root": os.geteuid() == 0, "kvm": os.path.exists("/dev/kvm")}


def install_missing(packages):
    if not packages:
        return
    runner.run(["apt-get", "update"])
    runner.run(["apt-get", "install", "-y"] + list(packages))
