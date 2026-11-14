"""Create a brand new Debian or Devuan base with mmdebstrap (or debootstrap).

The base is made for a platform (see platforms.py): a PC, an ARM64 machine with
UEFI, a Raspberry Pi or a RISC-V machine. For another processor than the one of
this computer, the programs of the new system run through qemu-user
(binfmt_misc): mmdebstrap and debootstrap then work exactly as for the PC.
"""

import os

from disco.core import distro, platforms, runner
from disco.core.apt import Sources, format_deb822, debian_sources
from disco.core.config import settings
from disco.core.log import log

BASE_PACKAGES = [
    "systemd-sysv", "live-boot", "live-config", "live-config-systemd", "sudo", "locales",
    "console-setup", "keyboard-configuration", "network-manager", "dbus", "polkitd",
    "firmware-linux-free", "plymouth", "plymouth-themes", "bash-completion", "ca-certificates",
    "less", "nano", "wget", "curl", "zstd", "pciutils", "usbutils",
]
# Only a live ISO needs these; an SD-card image is an installed system.
LIVE_ONLY = {"live-boot", "live-config", "live-config-systemd", "live-config-sysvinit"}
# Firmware for PCs (Wi-Fi, graphics); boards bring their own in the platform's packages.
PC_FIRMWARE = ["firmware-misc-nonfree", "firmware-realtek", "firmware-iwlwifi", "firmware-atheros",
               "firmware-amd-graphics"]
DEBIAN_KEYRING = "/usr/share/keyrings/debian-archive-keyring.gpg"
# Devuan has no systemd: the live system starts with sysvinit, elogind gives desktops their sessions.
DEVUAN_SWAP = {"systemd-sysv": "sysvinit-core", "live-config-systemd": "live-config-sysvinit"}
DEVUAN_EXTRA = ["elogind", "libpam-elogind"]
KERNEL = {p.arch: p.kernel for p in reversed(platforms.PLATFORMS)}
VARIANTS = ["important", "standard", "minbase"]


def packages_for(p, devuan=False, firmware=True):
    """The packages of a new base system for platform *p*."""
    base = [x for x in BASE_PACKAGES if p.output == "iso" or x not in LIVE_ONLY]
    if devuan:
        base = [DEVUAN_SWAP.get(x, x) for x in base] + DEVUAN_EXTRA
    out = base + [p.kernel] + list(p.packages)
    if firmware and p.arch in ("amd64", "i386"):
        out += PC_FIRMWARE
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def forget_build_host(project, fallback="debian"):
    """mmdebstrap and debootstrap copy this computer's host name and DNS servers into
    the new system: give it its own name and an empty resolv.conf (NetworkManager
    writes it when the system runs)."""
    from disco.core.branding import Branding
    rootfs = project.rootfs
    ident = project.state.get("identity", {})
    Branding(project).set_hostname(ident.get("hostname") or fallback, fallback)
    resolv = rootfs / "etc/resolv.conf"
    if resolv.is_file() and not resolv.is_symlink():
        resolv.write_text("")


def bootstrap(project, suite="stable", arch=None, variant="important", mirror=None,
              extra=(), firmware=True, devuan=False, platform_id=None, packages=None):
    """A new base system. *packages* replaces the default package set (packages_for).
    Debian bases start with systemd, Devuan bases with SysVinit; another init system
    is switched to afterwards (initsystem.use), which replaces it cleanly."""
    if suite not in ("stable", "testing", "sid", "oldstable"):
        raise ValueError("Only oldstable, stable, testing and sid can be bootstrapped")
    if variant not in VARIANTS:
        raise ValueError("Unknown variant: {}".format(variant))
    plat = platforms.get(platform_id) if platform_id else platforms.for_arch(arch or "amd64", "iso")
    arch = plat.arch
    cfg = settings()
    family = "Devuan" if devuan else "Debian"
    if platforms.is_foreign(arch):
        ok, how = platforms.enable_binfmt(arch)
        if not ok:
            raise RuntimeError(how)
        log.info("%s programs run through qemu-user on this %s computer (%s)", arch, platforms.host_arch(), how)
    if devuan:
        from disco.core.apt import devuan_codenames, devuan_sources
        codename = devuan_codenames()[suite]
        mirror = mirror or cfg.get("devuan", "mirror")
        keyring = cfg.get("devuan", "keyring")
        if not os.path.exists(keyring):
            raise RuntimeError("{} is missing on this computer: install the package devuan-keyring (from "
                               "deb.devuan.org/merged/pool/DEVUAN/main/d/devuan-keyring/) first".format(keyring))
    else:
        codename = cfg.suite_codenames()[suite] if suite != "sid" else "sid"
        mirror = mirror or cfg.get("debian", "mirror")
        if not os.path.exists(DEBIAN_KEYRING):
            raise RuntimeError("{} is missing on this computer: install the package debian-archive-keyring "
                               "first".format(DEBIAN_KEYRING))
    ok, why = platforms.release_ok(plat, codename)
    if not ok:
        raise ValueError(why)
    base = list(packages) if packages else packages_for(plat, devuan=devuan, firmware=firmware)
    packages = base + [x for x in extra if x and x not in base]
    rootfs = project.rootfs
    if rootfs.exists() and any(rootfs.iterdir()):
        from disco.core.chroot import Chroot, safe_rmtree
        Chroot(rootfs).force_release()
        safe_rmtree(rootfs)
    rootfs.mkdir(parents=True, exist_ok=True)
    components = cfg.get("devuan" if devuan else "debian", "components")
    if runner.which("mmdebstrap"):
        log.info("Bootstrapping %s %s (%s, %s) with mmdebstrap", family, suite, codename, arch)
        sources = format_deb822(devuan_sources(suite, mirror=mirror) if devuan else
                                debian_sources(suite, mirror=mirror))
        src_file = project.cache / "bootstrap.sources"
        src_file.write_text(sources)
        runner.run(["mmdebstrap", "--variant=" + variant, "--architectures=" + arch,
                    "--components=" + components.replace(" ", ","),
                    "--include=" + ",".join(packages),
                    "--aptopt=Acquire::Retries \"3\"",
                    codename, rootfs, src_file])
    elif runner.which("debootstrap"):
        log.info("Bootstrapping %s %s (%s, %s) with debootstrap", family, suite, codename, arch)
        # debootstrap has no "important"/"standard" variants: its default
        # installs required + important packages.
        variant_args = ["--variant=minbase"] if variant == "minbase" else []
        keyring_args = ["--keyring=" + cfg.get("devuan", "keyring")] if devuan else []
        runner.run(["debootstrap", "--arch=" + arch] + variant_args + keyring_args +
                   ["--components=" + components.replace(" ", ","),
                    "--include=" + ",".join(packages), codename, rootfs, mirror])
    else:
        raise RuntimeError("Install mmdebstrap (recommended) or debootstrap first")
    Sources(rootfs).set_debian(suite, mirror=mirror, devuan=devuan)
    (rootfs / "etc/apt/sources.list").write_text("# See /etc/apt/sources.list.d/{}.sources\n".format(
        "devuan" if devuan else "debian"))
    forget_build_host(project, "devuan" if devuan else "debian")
    info = distro.detect(rootfs)
    if info.suite == "unknown":
        info.suite = suite
    distro.validate(info, rootfs)
    project.state["source"].update({"kind": "bootstrap", "path": "{} {} {}".format(suite, codename, arch),
                                    "label": "{} {} ({}) for {}".format(family, suite, codename, plat.name),
                                    "boot_mode": "generate"})
    project.state.setdefault("builder", {})["platform"] = plat.id
    project.state["distro"] = info.to_dict()
    project.record("bootstrap", "{} {} {} {}".format(suite, codename, arch, variant))
    return info
