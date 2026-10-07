"""Rebuild the live ISO image from the customized root filesystem."""

import datetime
import hashlib
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from eduka_customizer.core import bootloader, cleanup, distro, iso, runner
from eduka_customizer.core.apt import Packages
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.config import data_file, settings
from eduka_customizer.core.log import log

COMPRESSORS = {
    # name: (min level, max level, default, level option)
    "zstd": (1, 22, 15, "-Xcompression-level"),
    "xz": (0, 0, 0, None),
    "gzip": (1, 9, 9, "-Xcompression-level"),
    "lz4": (0, 0, 0, None),
    "lzo": (1, 9, 8, "-Xcompression-level"),
}
KERNEL_PACKAGE = {"amd64": "linux-image-amd64", "i386": "linux-image-686-pae",
                  "arm64": "linux-image-arm64"}
LIVE_PACKAGES = ["live-boot", "live-config", "live-config-systemd"]


@dataclass
class BuildOptions:
    compression: str = "zstd"
    level: int = 15
    block_size: str = "1M"
    volume_label: str = "EDUKASAUN_OS"
    iso_name: str = "{id}-{version}-{suite}-{arch}-{date}.iso"
    title: str = "Edukasaun OS"
    boot_params: str = "quiet splash"
    timeout: int = 10
    reuse_squashfs: bool = False
    initramfs: str = "auto"          # auto | always | never
    remove_installer: bool = True    # drop Debian-Installer boot entries
    boot_mode: str = "auto"          # auto | replay | generate
    secure_boot: bool = True
    checksums: list = field(default_factory=lambda: ["sha256"])
    cleanup: dict = field(default_factory=cleanup.defaults)
    processors: int = 0

    @classmethod
    def from_project(cls, project):
        cfg = settings()
        o = cls(compression=cfg.get("build", "compression"),
                level=cfg.getint("build", "compression_level"),
                block_size=cfg.get("build", "block_size"),
                iso_name=cfg.get("build", "iso_name"),
                checksums=cfg.get("build", "checksums").split())
        ident = project.state.get("identity", {})
        o.volume_label = ident.get("volume_label") or o.volume_label
        o.title = ident.get("name") or o.title
        boot = project.state.get("boot", {})
        o.boot_params = boot.get("extra_params", o.boot_params)
        o.timeout = int(boot.get("timeout", o.timeout))
        for k, v in project.state.get("build", {}).items():
            if hasattr(o, k):
                setattr(o, k, v)
        return o

    def to_dict(self):
        return asdict(self)


def sanitize_label(label):
    label = re.sub(r"[^A-Za-z0-9_ .-]", "_", label.strip())[:32]
    return label or "EDUKASAUN_OS"


def iso_filename(template, project):
    info = project.distro
    ident = project.state.get("identity", {})
    values = {
        "id": ident.get("id") or "edukasaun",
        "name": ident.get("name") or "Edukasaun-OS",
        "version": ident.get("version") or "0",
        "codename": (ident.get("codename") or "").lower(),
        "suite": info.suite or "debian",
        "debian": info.debian_codename or "",
        "arch": info.arch or "amd64",
        "date": datetime.date.today().strftime("%Y%m%d"),
    }
    try:
        name = template.format(**values)
    except (KeyError, IndexError, ValueError):
        name = "{id}-{version}-{arch}-{date}.iso".format(**values)
    name = re.sub(r"[^A-Za-z0-9._+-]", "-", name).strip("-")
    if not name.endswith(".iso"):
        name += ".iso"
    return name


def tree_size(path, excludes=()):
    total = 0
    for root, dirs, files in os.walk(path):
        rel = os.path.relpath(root, path)
        if rel.split(os.sep)[0] in excludes:
            dirs[:] = []
            continue
        for f in files:
            try:
                st = os.lstat(os.path.join(root, f))
            except OSError:
                continue
            if not os.path.islink(os.path.join(root, f)):
                total += st.st_size
    return total


def hash_file(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def squashfs_args(opts, arch):
    comp = opts.compression if opts.compression in COMPRESSORS else "zstd"
    lo, hi, default, flag = COMPRESSORS[comp]
    args = ["-comp", comp, "-b", opts.block_size or "1M"]
    if flag:
        level = int(opts.level or default)
        args += [flag, str(min(hi, max(lo, level)))]
    if comp == "xz":
        if arch in ("amd64", "i386"):
            args += ["-Xbcj", "x86"]
        elif arch in ("arm64", "armhf"):
            args += ["-Xbcj", "arm"]
        args += ["-Xdict-size", "100%"]
    if comp == "lz4":
        args += ["-Xhc"]
    if opts.processors:
        args += ["-processors", str(opts.processors)]
    return args


def label_dependencies(project):
    """Return True if a boot config searches the ISO by its volume label."""
    pattern = re.compile(r"(--label|search\.fs_label|LABEL=|root=live:)")
    for f in bootloader.config_files(project.isodir):
        if pattern.search(f.read_text(errors="replace")):
            return True
    img = project.isodir / "boot/grub/efi.img"
    if img.exists() and runner.which("mtype"):
        listing = runner.output(["mdir", "-/", "-b", "-i", img, "::/"], check=False)
        for path in listing.split():
            if path.lower().endswith(".cfg"):
                rel = path.split(":", 1)[-1]
                text = runner.output(["mtype", "-i", img, "::" + rel], check=False)
                if pattern.search(text):
                    return True
    return False


class Builder:
    def __init__(self, project, opts=None, progress=None, stage=None):
        self.project = project
        self.opts = opts or BuildOptions.from_project(project)
        self.progress = progress or (lambda pct: None)
        self.stage = stage or (lambda text: log.info("== %s ==", text))
        self.chroot = Chroot(project.rootfs)
        self.started = time.time()

    # Steps ----------------------------------------------------------------
    def check(self):
        self.stage("Checking the root filesystem")
        p = self.project
        if not p.has_rootfs():
            raise RuntimeError("The project has no root filesystem yet. Extract an ISO or "
                               "bootstrap a new base first.")
        info = distro.detect(p.rootfs)
        distro.validate(info, p.rootfs)
        p.state["distro"] = info.to_dict()
        p.save()
        log.info("Building %s", info.summary())
        runner.require("mksquashfs", "xorriso")

    def ensure_live_stack(self):
        rootfs = self.project.rootfs
        pkgs = Packages(self.project)
        missing = [x for x in LIVE_PACKAGES if not pkgs.is_installed(x)]
        if not list(Path(rootfs, "boot").glob("vmlinuz-*")):
            missing.append(KERNEL_PACKAGE.get(self.project.distro.arch, "linux-image-amd64"))
        if missing:
            self.stage("Installing live boot support")
            log.info("Missing for a bootable live system: %s", " ".join(missing))
            pkgs.install(missing)

    def initramfs(self):
        mode = self.opts.initramfs
        dirty = self.project.state.get("initramfs_dirty")
        kernels = cleanup.kernels(self.project.rootfs)
        newest = kernels[-1] if kernels else None
        initrd_ok = newest and Path(self.project.rootfs, "boot/initrd.img-" + newest).exists()
        if mode == "never" and initrd_ok:
            return
        if mode == "always" or dirty or not initrd_ok:
            self.stage("Updating initramfs")
            if initrd_ok:
                self.chroot.run(["update-initramfs", "-u", "-k", "all"])
            else:
                self.chroot.run(["update-initramfs", "-c", "-k", newest])
            self.project.state["initramfs_dirty"] = False
            self.project.save()

    def boot_files(self):
        self.stage("Preparing boot files")
        p = self.project
        kernels = cleanup.kernels(p.rootfs)
        wanted = p.state.get("boot", {}).get("kernel")
        version = wanted if wanted in kernels else (kernels[-1] if kernels else None)
        if not version:
            raise RuntimeError("No kernel found in /boot of the root filesystem")
        vmlinuz = p.rootfs / "boot" / ("vmlinuz-" + version)
        initrd = p.rootfs / "boot" / ("initrd.img-" + version)
        if not initrd.exists():
            raise RuntimeError("initrd.img-{} is missing".format(version))
        live = p.isodir / "live"
        live.mkdir(parents=True, exist_ok=True)
        for old in list(live.glob("vmlinuz*")) + list(live.glob("initrd*")):
            old.unlink()
        shutil.copy2(vmlinuz, live / "vmlinuz")
        shutil.copy2(initrd, live / "initrd.img")
        log.info("Kernel %s", version)

        mode = self.boot_mode()
        params = self.opts.boot_params
        if mode == "generate":
            bootloader.BootGenerator(p).generate(self.opts.title, params, self.opts.timeout,
                                                 self.opts.secure_boot)
            if p.state.get("boot", {}).get("splash") and Path(p.state["boot"]["splash"]).exists():
                bootloader.set_splash(p.isodir, p.state["boot"]["splash"])
        else:
            bootloader.normalize_kernel_paths(p.isodir)
            if self.opts.remove_installer:
                if bootloader.remove_installer_entries(p.isodir):
                    log.info("Removed Debian-Installer boot entries (Calamares installs the live system)")
                for d in ("install", "install.amd", "d-i"):
                    if (p.isodir / d).is_dir():
                        shutil.rmtree(p.isodir / d)
            bootloader.append_params(p.isodir, params)
            bootloader.set_titles(p.isodir, self.opts.title)
            bootloader.set_timeout(p.isodir, self.opts.timeout)
            splash = p.state.get("boot", {}).get("splash")
            if splash and Path(splash).exists():
                bootloader.set_splash(p.isodir, splash)
        info = p.distro
        disk_info = p.isodir / ".disk/info"
        disk_info.parent.mkdir(parents=True, exist_ok=True)
        disk_info.write_text('{} {} "{}" - {} {} ({})\n'.format(
            self.opts.title, p.state["identity"].get("version", ""),
            p.state["identity"].get("codename", ""), info.suite, info.arch,
            datetime.date.today().strftime("%Y%m%d")))

    def boot_mode(self):
        mode = self.opts.boot_mode
        if mode == "auto":
            mode = self.project.state.get("source", {}).get("boot_mode") or "replay"
        if mode == "replay" and not iso.load_replay(self.project):
            mode = "generate"
        return mode

    def manifests(self):
        p = self.project
        pkgs = Packages(p).installed()
        (p.isodir / "live/filesystem.packages").write_text(
            "".join("{}\t{}\n".format(n, v) for n, v, _s, _d in pkgs))
        size = tree_size(p.rootfs, excludes=("proc", "sys", "dev", "run", "tmp"))
        (p.isodir / "live/filesystem.size").write_text(str(size) + "\n")
        log.info("%d packages, %.2f GiB uncompressed", len(pkgs), size / 1024 ** 3)
        return size

    def check_space(self, size):
        free = shutil.disk_usage(self.project.output).free
        need = int(size * 0.9) + 512 * 1024 ** 2
        if free < need:
            raise RuntimeError("Not enough free disk space: {:.1f} GiB free, about {:.1f} GiB "
                               "needed.".format(free / 1024 ** 3, need / 1024 ** 3))

    def squashfs(self):
        p = self.project
        target = p.isodir / "live/filesystem.squashfs"
        if self.opts.reuse_squashfs and target.exists():
            log.info("Reusing existing filesystem.squashfs")
            return
        self.stage("Compressing the root filesystem ({})".format(self.opts.compression))
        if target.exists():
            target.unlink()
        args = ["mksquashfs", p.rootfs, target, "-noappend", "-wildcards",
                "-ef", data_file("exclude.list"), "-e", "boot/efi"]
        args += squashfs_args(self.opts, p.distro.arch)
        runner.run(args, progress=self.progress)
        log.info("filesystem.squashfs: %.2f GiB", target.stat().st_size / 1024 ** 3)

    def tree_checksums(self):
        self.stage("Writing checksums of the ISO contents")
        p = self.project
        skip = {"md5sum.txt", "sha256sum.txt", "SHA256SUMS", "MD5SUMS"}
        skip_rel = {"isolinux/isolinux.bin", "isolinux/boot.cat", "boot/grub/efi.img"}
        targets = [n for n in ("sha256sum.txt", "md5sum.txt") if (p.isodir / n).exists()] or ["sha256sum.txt"]
        files = []
        for root, _dirs, names in os.walk(p.isodir):
            for n in names:
                full = Path(root, n)
                rel = full.relative_to(p.isodir).as_posix()
                if n in skip or rel in skip_rel or full.is_symlink():
                    continue
                files.append(rel)
        files.sort()
        for target in targets:
            algo = "md5" if target.startswith("md5") else "sha256"
            with open(p.isodir / target, "w") as fh:
                for rel in files:
                    runner.check_cancel()
                    fh.write("{}  ./{}\n".format(hash_file(p.isodir / rel, algo), rel))

    def xorriso(self):
        self.stage("Creating the ISO image")
        p = self.project
        name = iso_filename(self.opts.iso_name, p)
        out = p.output / name
        if out.exists():
            out.unlink()
        label = sanitize_label(self.opts.volume_label)
        mode = self.boot_mode()
        if mode == "replay":
            if label_dependencies(p):
                original = iso.iso_volume_id(p.state["source"]["path"]) if Path(
                    p.state["source"].get("path", "")).exists() else ""
                stored = p.state["source"].get("volume_id") or original
                if stored:
                    log.warning("The boot menu finds the ISO by its label; keeping '%s'", stored)
                    label = stored
            args = ["-as", "mkisofs"] + iso.load_replay(p)
            for opt in ("-r", "-J", "-joliet-long"):
                if opt not in args:
                    args.append(opt)
            if "-iso-level" not in args:
                args += ["-iso-level", "3"]
            args += ["-V", label]
        else:
            args = ["-as", "mkisofs"] + bootloader.BootGenerator(p).xorriso_args(label)
        args += ["-publisher", "Edukasaun OS", "-preparer", "Eduka-Customizer",
                 "-o", out, p.isodir]
        runner.run(["xorriso"] + args, progress=self.progress)
        return out

    def iso_checksums(self, out):
        for algo in self.opts.checksums or ["sha256"]:
            if algo not in ("md5", "sha1", "sha256", "sha512"):
                continue
            digest = hash_file(out, algo)
            Path(str(out) + "." + algo).write_text("{}  {}\n".format(digest, out.name))
            log.info("%s: %s", algo.upper(), digest)

    # Driver ---------------------------------------------------------------------
    def run(self):
        p = self.project
        self.check()
        with self.chroot:
            self.ensure_live_stack()
            self.initramfs()
            self.stage("Cleaning up")
            cleanup.run(p, self.opts.cleanup)
        self.boot_files()
        size = self.manifests()
        self.check_space(size)
        self.squashfs()
        self.tree_checksums()
        out = self.xorriso()
        self.iso_checksums(out)
        p.state["last_iso"] = str(out)
        p.state["build"] = self.opts.to_dict()
        p.record("build", out.name)
        minutes = (time.time() - self.started) / 60
        log.info("Done: %s (%.2f GiB, %.1f min)", out, out.stat().st_size / 1024 ** 3, minutes)
        return out


def build(project, opts=None, progress=None, stage=None):
    return Builder(project, opts, progress, stage).run()
