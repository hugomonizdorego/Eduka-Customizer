"""Create a brand new Debian base with mmdebstrap (or debootstrap)."""

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
KERNEL = {"amd64": "linux-image-amd64", "i386": "linux-image-686-pae", "arm64": "linux-image-arm64"}
VARIANTS = ["important", "standard", "minbase"]


def bootstrap(project, suite="stable", arch="amd64", variant="important", mirror=None,
              extra=(), firmware=True):
    if suite not in ("stable", "testing", "sid"):
        raise ValueError("Only stable, testing and sid can be bootstrapped")
    if variant not in VARIANTS:
        raise ValueError("Unknown variant: {}".format(variant))
    cfg = settings()
    codename = cfg.suite_codenames()[suite]
    mirror = mirror or cfg.get("debian", "mirror")
    packages = BASE_PACKAGES + [KERNEL.get(arch, "linux-image-amd64")] + list(extra)
    if firmware:
        packages += ["firmware-misc-nonfree", "firmware-realtek", "firmware-iwlwifi",
                     "firmware-atheros", "firmware-amd-graphics"]
    rootfs = project.rootfs
    if rootfs.exists() and any(rootfs.iterdir()):
        from eduka_customizer.core.chroot import Chroot, safe_rmtree
        Chroot(rootfs).force_release()
        safe_rmtree(rootfs)
    rootfs.mkdir(parents=True, exist_ok=True)
    components = cfg.get("debian", "components")
    if runner.which("mmdebstrap"):
        log.info("Bootstrapping Debian %s (%s, %s) with mmdebstrap", suite, codename, arch)
        sources = format_deb822(debian_sources(suite, mirror=mirror))
        src_file = project.cache / "bootstrap.sources"
        src_file.write_text(sources)
        runner.run(["mmdebstrap", "--variant=" + variant, "--architectures=" + arch,
                    "--components=" + components.replace(" ", ","),
                    "--include=" + ",".join(packages),
                    "--aptopt=Acquire::Retries \"3\"",
                    codename, rootfs, src_file])
    elif runner.which("debootstrap"):
        log.info("Bootstrapping Debian %s (%s, %s) with debootstrap", suite, codename, arch)
        # debootstrap has no "important"/"standard" variants: its default
        # installs required + important packages.
        variant_args = ["--variant=minbase"] if variant == "minbase" else []
        runner.run(["debootstrap", "--arch=" + arch] + variant_args +
                   ["--components=" + components.replace(" ", ","),
                    "--include=" + ",".join(packages), codename, rootfs, mirror])
    else:
        raise RuntimeError("Install mmdebstrap (recommended) or debootstrap first")
    Sources(rootfs).set_debian(suite, mirror=mirror)
    (rootfs / "etc/apt/sources.list").write_text("# See /etc/apt/sources.list.d/debian.sources\n")
    info = distro.detect(rootfs)
    if info.suite == "unknown":
        info.suite = suite
    distro.validate(info, rootfs)
    project.state["source"].update({"kind": "bootstrap", "path": "{} {} {}".format(suite, codename, arch),
                                    "label": "Debian {} ({})".format(suite, codename),
                                    "boot_mode": "generate"})
    project.state["distro"] = info.to_dict()
    project.record("bootstrap", "{} {} {} {}".format(suite, codename, arch, variant))
    return info
