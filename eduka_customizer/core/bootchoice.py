"""The boot loader Calamares installs on the computer.

Only boot loaders that are maintained, packaged by Debian and supported by
Calamares can be chosen; their packages come from the Debian archive of the
image. The others are listed with the reason they cannot be used. The live
ISO itself keeps GRUB (UEFI) and ISOLINUX (BIOS), and BIOS computers always
get GRUB: Calamares installs GRUB whenever the firmware is not UEFI.
"""

import re
from pathlib import Path

from eduka_customizer.core import calamares_check
from eduka_customizer.core.log import log

# id, name, description, Calamares efiBootLoader, Debian packages, minimum Calamares, needed files
LOADERS = [
    ("grub", "GRUB", "Debian's boot loader: BIOS and UEFI, menus, themes, every operating system. Recommended.",
     "grub", ["grub-efi-amd64", "efibootmgr"], (3, 2), ["usr/sbin/grub-install"]),
    ("grub-secureboot", "GRUB with Secure Boot", "GRUB signed by Debian through shim: boots with Secure Boot "
     "switched on.", "sb-shim", ["grub-efi-amd64-signed", "shim-signed", "efibootmgr"], (3, 2),
     ["usr/sbin/grub-install"]),
    ("systemd-boot", "systemd-boot", "Simple and fast UEFI boot manager, part of systemd. UEFI only "
     "(BIOS computers get GRUB).", "systemd-boot", ["systemd-boot", "efibootmgr"], (3, 2),
     ["usr/bin/bootctl", "usr/bin/kernel-install"]),
    ("refind", "rEFInd", "Graphical UEFI boot manager with themes, finds every system by itself. UEFI only "
     "(BIOS computers get GRUB). Needs Calamares 3.3 or newer.", "refind", ["refind", "efibootmgr"], (3, 3),
     ["usr/sbin/refind-install"]),
]
NOT_AVAILABLE = [
    ("lilo", "LILO", "Development stopped in 2015; no UEFI and no modern file systems. Not in Debian any more."),
    ("burg", "BURG", "A GRUB fork that is no longer developed (since 2012) and is not packaged by Debian."),
    ("efistub", "EFISTUB", "The kernel can start directly from UEFI, but Calamares has no module to set it up "
                           "and every kernel update needs new firmware entries."),
    ("syslinux", "Syslinux / EXTLINUX", "Used for the BIOS menu of the live ISO already; Calamares cannot "
                                        "install it on a computer."),
]
PRESEED = {"refind": "refind refind/install_to_esp boolean false\n"}


def loader(loader_id):
    for entry in LOADERS:
        if entry[0] == loader_id:
            return entry
    raise KeyError("Unknown boot loader: {}".format(loader_id))


class BootChoice:
    def __init__(self, project):
        self.project = project
        self.rootfs = Path(project.rootfs)

    def calamares_version(self):
        return calamares_check._version(self.rootfs)

    def options(self):
        """[(id, name, description, usable, reason)] for the GUI."""
        version = self.calamares_version()
        out = []
        for lid, name, desc, _cal, _pk, minimum, _files in LOADERS:
            usable, reason = True, ""
            if version and version < minimum:
                usable, reason = False, "needs Calamares {}.{} (the image has {}.{})".format(
                    minimum[0], minimum[1], version[0], version[1])
            out.append((lid, name, desc, usable, reason))
        for lid, name, why in NOT_AVAILABLE:
            out.append((lid, name, why, False, why))
        return out

    def current(self):
        p = self.rootfs / "etc/calamares/modules/bootloader.conf"
        if p.exists():
            m = re.search(r'(?m)^efiBootLoader:\s*"?([a-z-]+)"?', p.read_text(errors="replace"))
            if m:
                return {"grub": "grub", "sb-shim": "grub-secureboot", "systemd-boot": "systemd-boot",
                        "refind": "refind"}.get(m.group(1), m.group(1))
        return self.project.state.get("boot", {}).get("installed_loader", "grub")

    def apply(self, loader_id, timeout=None):
        """Install the packages of *loader_id* into the image and make Calamares use it."""
        lid, name, _d, cal_name, packages, minimum, files = loader(loader_id)
        version = self.calamares_version()
        if version and version < minimum:
            raise ValueError("{} needs Calamares {}.{}; the image has {}.{}".format(name, minimum[0], minimum[1],
                                                                                    version[0], version[1]))
        from eduka_customizer.core.apt import Packages
        from eduka_customizer.core.calamares import Calamares
        pk = Packages(self.project)
        with pk.chroot:
            if lid in PRESEED:
                pk.chroot.run(["debconf-set-selections"], input=PRESEED[lid], check=False)
            missing = [p for p in packages if not pk.is_installed(p)]
            if missing:
                pk.update()
                have = pk.available(missing)
                lacking = [p for p in missing if p not in have]
                if lacking:
                    raise RuntimeError("{} is not available from the Debian archive of the image: {}".format(
                        name, " ".join(lacking)))
                pk.install(missing, update=False)
        absent = [f for f in files if not (self.rootfs / f).exists()]
        if absent:
            raise RuntimeError("{} is installed but /{} is missing".format(name, absent[0]))
        cal = Calamares(self.project)
        if cal.installed():
            values = {"efiBootLoader": cal_name}
            if timeout not in (None, ""):
                values["timeout"] = str(int(timeout))
            cal.write("bootloader", values)
        else:
            log.warning("Calamares is not installed: the choice is stored and used when it is")
        self.project.state.setdefault("boot", {})["installed_loader"] = lid
        self.project.save()
        self.project.record("installed-boot-loader", lid)
        log.info("Boot loader of installed systems: %s", name)
