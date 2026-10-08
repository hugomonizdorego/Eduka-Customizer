"""Create a brand new Debian or Devuan base with mmdebstrap (or debootstrap)."""

import os

from eduka_customizer.core import distro, runner
from eduka_customizer.core.apt import Sources, format_deb822, debian_sources
from eduka_customizer.core.config import settings
from eduka_customizer.core.log import log

BASE_PACKAGES = [
    "systemd-sysv", "live-boot", "live-config", "live-config-systemd", "sudo", "locales",
    "console-setup", "keyboard-configuration", "network-manager", "dbus", "polkitd",
    "firmware-linux-free", "plymouth", "plymouth-themes", "bash-completion", "ca-certificates",
    "less", "nano", "wget", "curl", "zstd", "pciutils", "usbutils",
]
# Devuan has no systemd: the live system starts with sysvinit, elogind gives desktops their sessions.
DEVUAN_SWAP = {"systemd-sysv": "sysvinit-core", "live-config-systemd": "live-config-sysvinit"}
DEVUAN_EXTRA = ["elogind", "libpam-elogind"]
KERNEL = {"amd64": "linux-image-amd64", "i386": "linux-image-686-pae", "arm64": "linux-image-arm64"}
VARIANTS = ["important", "standard", "minbase"]


def bootstrap(project, suite="stable", arch="amd64", variant="important", mirror=None,
              extra=(), firmware=True, devuan=False):
    if suite not in ("stable", "testing", "sid"):
        raise ValueError("Only stable, testing and sid can be bootstrapped")
    if variant not in VARIANTS:
        raise ValueError("Unknown variant: {}".format(variant))
    cfg = settings()
    family = "Devuan" if devuan else "Debian"
    if devuan:
        from eduka_customizer.core.apt import devuan_codenames, devuan_sources
        codename = devuan_codenames()[suite]
        mirror = mirror or cfg.get("devuan", "mirror")
        keyring = cfg.get("devuan", "keyring")
        if not os.path.exists(keyring):
            raise RuntimeError("{} is missing on this computer: install the package devuan-keyring (from "
                               "deb.devuan.org/merged/pool/DEVUAN/main/d/devuan-keyring/) first".format(keyring))
        base = [DEVUAN_SWAP.get(p, p) for p in BASE_PACKAGES] + DEVUAN_EXTRA
    else:
        codename = cfg.suite_codenames()[suite]
        mirror = mirror or cfg.get("debian", "mirror")
        base = list(BASE_PACKAGES)
    packages = base + [KERNEL.get(arch, "linux-image-amd64")] + list(extra)
    if firmware:
        packages += ["firmware-misc-nonfree", "firmware-realtek", "firmware-iwlwifi",
                     "firmware-atheros", "firmware-amd-graphics"]
    rootfs = project.rootfs
    if rootfs.exists() and any(rootfs.iterdir()):
        from eduka_customizer.core.chroot import Chroot, safe_rmtree
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
    info = distro.detect(rootfs)
    if info.suite == "unknown":
        info.suite = suite
    distro.validate(info, rootfs)
    project.state["source"].update({"kind": "bootstrap", "path": "{} {} {}".format(suite, codename, arch),
                                    "label": "{} {} ({})".format(family, suite, codename),
                                    "boot_mode": "generate"})
    project.state["distro"] = info.to_dict()
    project.record("bootstrap", "{} {} {} {}".format(suite, codename, arch, variant))
    return info
