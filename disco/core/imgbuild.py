"""SD-card images for boards (Raspberry Pi 1 to 5).

An image is an installed system, not a live one. Its layout is the one of
Debian's own Raspberry Pi images:

  partition 1  FAT32, label RASPIFIRM, mounted at /boot/firmware:
               the Raspberry Pi firmware, the kernel, the initrd, the device
               trees, config.txt and cmdline.txt (from Debian's raspi-firmware)
  partition 2  ext4, label RASPIROOT: the system

The partitions are made as files and written into the image with dd: the FAT
partition with mkfs.vfat and mtools, the system with `mkfs.ext4 -d`, which
copies the root filesystem while it makes the file system. Nothing is mounted
with loop devices, so it also works where loop devices are not allowed. The
partition table is written with sfdisk. On the first start the system
partition grows to the whole card.
"""

import hashlib
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from disco.core import cleanup, platforms, runner
from disco.core.apt import Packages
from disco.core.chroot import Chroot, check_released
from disco.core.config import data_file
from disco.core.log import log

LABEL_BOOT = "RASPIFIRM"
LABEL_ROOT = "RASPIROOT"
FIRMWARE = "boot/firmware"
START_MB = 4             # where the first partition starts (like Debian's images)
FIRSTBOOT = "usr/lib/disco-firstboot/disco-firstboot"
FIRSTBOOT_UNIT = "etc/systemd/system/disco-firstboot.service"
FIRSTBOOT_SERVICE = """[Unit]
Description=First start of the SD-card image (whole card, SSH keys, sysconf.txt)
DefaultDependencies=no
After=local-fs.target
Before=ssh.service display-manager.service systemd-user-sessions.service
ConditionPathExists=!/var/lib/disco-firstboot.done

[Service]
Type=oneshot
ExecStart=/usr/lib/disco-firstboot/disco-firstboot
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
SSH_GUARD = "etc/ssh/sshd_config.d/60-disco-default-password.conf"
SSH_GUARD_TEXT = """# Written by D!sco. The account {user} has the well-known password of the image
# ({what}). Over the network it logs in with an SSH key only: put your key into
# sysconf.txt (root_authorized_key) or ~/.ssh/authorized_keys. Set a password of
# your own (passwd), then delete this file to allow password logins again.
Match User {user}
    PasswordAuthentication no
    KbdInteractiveAuthentication no
"""
FSTAB = """# /etc/fstab of an SD-card image made with D!sco
LABEL={root}\t/\text4\trw,errors=remount-ro\t0\t1
LABEL={boot}\t/boot/firmware\tvfat\trw,umask=0022\t0\t2
"""
SYSCONF = """# Settings for the first start of this SD card. Edit this file on any computer
# before you start the card for the first time; they are applied once.
#hostname=mypi
#root_authorized_key=ssh-ed25519 AAAA... you@computer
"""
CONFIG_TXT = """# config.txt written by D!sco ({name}); Debian's raspi-firmware writes it again
# after every kernel update. Your own lines live in /etc/default/raspi-firmware-custom.
[all]
{arm64}upstream_kernel=1
enable_uart=1
kernel={kernel}
initramfs {initrd} followkernel
disable_fw_kms_setup=1
{custom}"""
SAFE_LINE = re.compile(r"^[A-Za-z0-9_.,:=/@+\- #\[\]*]*$")


@dataclass
class ImageOptions:
    size_mb: int = 0            # 0: as small as possible; the card is used fully after the first start
    boot_mb: int = 512
    compress: str = "xz"        # xz | none
    config_txt: str = ""        # extra lines for config.txt (raspi-firmware-custom)
    cmdline: str = ""           # extra kernel options (raspi-extra-cmdline)
    sysconf: bool = True        # sysconf.txt on the boot partition
    name: str = ""              # file name of the image (.img)

    @classmethod
    def from_project(cls, project):
        o = cls()
        for k, v in project.state.get("board", {}).items():
            if hasattr(o, k):
                setattr(o, k, v)
        return o

    def to_dict(self):
        return asdict(self)


def check_lines(text, what):
    """Lines for config.txt or cmdline.txt: plain settings only (no quotes or shell characters)."""
    lines = [l.rstrip() for l in (text or "").splitlines()]
    bad = [l for l in lines if l and not SAFE_LINE.match(l)]
    if bad:
        raise ValueError("{}: only letters, digits and = , . : / @ + - # [ ] * are allowed ('{}')".format(
            what, bad[0][:60]))
    return "\n".join(l for l in lines if l)


class ImageBuilder:
    def __init__(self, project, opts=None, progress=None, stage=None):
        self.project = project
        self.rootfs = Path(project.rootfs)
        self.opts = opts or ImageOptions.from_project(project)
        self.progress = progress or (lambda pct: None)
        self.stage = stage or (lambda text: log.info("== %s ==", text))
        self.platform = platforms.of_project(project)
        self.chroot = Chroot(project.rootfs)

    # Inside the system ------------------------------------------------------------------------
    def kernels(self):
        return cleanup.kernels(self.rootfs)

    def ensure_packages(self):
        pk = Packages(self.project)
        want = [self.platform.kernel] + [p for p in self.platform.packages if p]
        missing = [p for p in want if not pk.is_installed(p)]
        if missing or not self.kernels():
            self.stage("Installing the kernel and the Raspberry Pi firmware")
            pk.install(missing or [self.platform.kernel])

    def configure(self):
        """fstab, raspi-firmware settings and the first start."""
        r = self.rootfs
        (r / FIRMWARE).mkdir(parents=True, exist_ok=True)
        (r / "etc/fstab").write_text(FSTAB.format(root=LABEL_ROOT, boot=LABEL_BOOT))
        default = r / "etc/default/raspi-firmware"
        default.parent.mkdir(parents=True, exist_ok=True)
        text = default.read_text(errors="replace") if default.exists() else ""
        if re.search(r"(?m)^#?\s*ROOTPART=", text):
            text = re.sub(r"(?m)^#?\s*ROOTPART=.*$", "ROOTPART=LABEL=" + LABEL_ROOT, text)
        else:
            text += "\nROOTPART=LABEL={}\n".format(LABEL_ROOT)
        default.write_text(text)
        custom = check_lines(self.opts.config_txt, "config.txt")
        extra = " ".join(check_lines(self.opts.cmdline, "cmdline.txt").split())
        (r / "etc/default/raspi-firmware-custom").write_text(
            "# Lines added to config.txt (D!sco, Raspberry Pi tab)\n" + (custom + "\n" if custom else ""))
        (r / "etc/default/raspi-extra-cmdline").write_text(extra + "\n" if extra else "")
        # The first start: whole card, keys, sysconf.txt.
        script = r / FIRSTBOOT
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data_file("board", "disco-firstboot"), script)
        script.chmod(0o755)
        unit = r / FIRSTBOOT_UNIT
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(FIRSTBOOT_SERVICE)
        wants = r / "etc/systemd/system/multi-user.target.wants/disco-firstboot.service"
        wants.parent.mkdir(parents=True, exist_ok=True)
        if wants.is_symlink() or wants.exists():
            wants.unlink()
        wants.symlink_to("/" + FIRSTBOOT_UNIT)
        from disco.core import initsystem
        initsystem.sync_services(self.project, self.chroot)
        hostname = (r / "etc/hostname").read_text().strip() if (r / "etc/hostname").exists() else ""
        if not hostname or hostname == "localhost":
            (r / "etc/hostname").write_text(self.project.os_id() + "\n")

    def default_user(self):
        """The user of the live system becomes a normal account of the image (there is no live-config)."""
        from disco.core.users import Users
        u = Users(self.project)
        live = u.live()
        name = live["username"]
        if name in ("user",) and not live["configured"]:
            log.info("No user chosen on the Users page: the image gets the account 'user' with the password "
                     "'live'")
        if not u._exists(name):
            password, password_hash = None, None
            script = u._script()
            if live["password"] == "default":
                password = "live"
            elif live["password"] == "custom" and script.exists():
                m = re.search(r"usermod -p '([^']+)'", script.read_text(errors="replace"))
                password_hash = m.group(1) if m else None
            u.add_account(name, live["fullname"], password=password, admin=True, groups=live["groups"],
                          password_hash=password_hash)
        self._guard_ssh(name, live["password"])
        if live["autologin"]:
            self._autologin(name)

    def _guard_ssh(self, user, mode):
        """A card on a network must not accept the well-known password (or no password) over SSH."""
        from disco.core.distro import resolve_in_root
        p = resolve_in_root(self.rootfs, SSH_GUARD)
        root = os.path.realpath(str(self.rootfs))
        if p is None or not os.path.realpath(str(p)).startswith(root.rstrip("/") + "/"):
            raise RuntimeError("/{} leads out of the system".format(SSH_GUARD))
        if mode in ("default", "none"):
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.is_symlink():
                p.unlink()
            p.write_text(SSH_GUARD_TEXT.format(user=user, what="'live'" if mode == "default" else "no password"))
            log.warning("The account %s has %s: change it after the first start (passwd). Over SSH it logs in "
                        "with a key only.", user, "the password 'live'" if mode == "default" else "no password")
        elif p.exists() or p.is_symlink():
            p.unlink()                  # a password of your own: password logins are fine

    def _autologin(self, user):
        r = self.rootfs
        if (r / "usr/sbin/lightdm").exists():
            p = r / "etc/lightdm/lightdm.conf.d/60-disco-autologin.conf"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("[Seat:*]\nautologin-user={}\nautologin-user-timeout=0\n".format(user))
            self.chroot.run(["groupadd", "-f", "-r", "autologin"], check=False, quiet=True)
            self.chroot.run(["gpasswd", "-a", user, "autologin"], check=False, quiet=True)
        if (r / "usr/bin/sddm").exists():
            p = r / "etc/sddm.conf.d/60-disco-autologin.conf"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("[Autologin]\nUser={}\n".format(user))

    def initramfs(self):
        ks = self.kernels()
        if not ks:
            raise RuntimeError("No kernel in /boot: install {} first".format(self.platform.kernel))
        newest = ks[-1]
        if not (self.rootfs / "boot" / ("initrd.img-" + newest)).exists() or self.project.state.get("initramfs_dirty"):
            self.stage("Updating the initramfs")
            self.chroot.run(["update-initramfs", "-u", "-k", "all"] if (self.rootfs / "boot" / (
                "initrd.img-" + newest)).exists() else ["update-initramfs", "-c", "-k", newest])
            self.project.state["initramfs_dirty"] = False
            self.project.save()

    def firmware(self):
        """Fill /boot/firmware with Debian's raspi-firmware hooks (they also run after kernel updates)."""
        self.stage("Writing the boot partition (firmware, kernel, config.txt, cmdline.txt)")
        r = self.rootfs
        fw = r / FIRMWARE
        fw.mkdir(parents=True, exist_ok=True)
        newest = self.kernels()[-1]
        hooks = [("etc/kernel/postinst.d", [newest, "/boot/vmlinuz-" + newest]),
                 ("etc/initramfs/post-update.d", [newest, "/boot/initrd.img-" + newest])]
        ran = False
        # The hooks only write into /boot/firmware when it is a mount point, as on the board.
        runner.run(["mount", "--bind", str(fw), str(fw)], quiet=True)
        try:
            for d, args in hooks:
                for hook in sorted(Path(r, d).glob("*raspi-firmware*")):
                    self.chroot.run(["/" + str(hook.relative_to(r))] + args, check=False)
                    ran = True
        finally:
            runner.run(["umount", "-l", str(fw)], check=False, quiet=True, cancellable=False)
        if not ran or not (fw / "config.txt").exists() or not list(fw.glob("vmlinuz*")):
            log.warning("raspi-firmware did not write the boot partition: D!sco writes it the same way")
            self._firmware_fallback(newest)

    def _firmware_fallback(self, version):
        r = self.rootfs
        fw = r / FIRMWARE
        blobs = r / "usr/lib/raspi-firmware"
        if not blobs.is_dir() or not any(blobs.iterdir()):
            raise RuntimeError("The Raspberry Pi firmware is missing (/usr/lib/raspi-firmware): install the package "
                               "raspi-firmware (component non-free-firmware)")
        for f in blobs.iterdir():
            if f.is_file():
                shutil.copy2(f, fw / f.name)
            elif f.is_dir():
                shutil.copytree(f, fw / f.name, dirs_exist_ok=True)
        dtbs = r / "usr/lib/linux-image-{}".format(version)
        for dtb in list(dtbs.glob("broadcom/bcm27*.dtb")) + list(dtbs.glob("bcm27*.dtb")) + \
                list(dtbs.glob("broadcom/bcm2712*.dtb")):
            shutil.copy2(dtb, fw / dtb.name)
        shutil.copy2(r / "boot" / ("vmlinuz-" + version), fw / ("vmlinuz-" + version))
        initrd = r / "boot" / ("initrd.img-" + version)
        if initrd.exists():
            shutil.copy2(initrd, fw / initrd.name)
        custom = check_lines(self.opts.config_txt, "config.txt")
        (fw / "config.txt").write_text(CONFIG_TXT.format(
            name=self.project.display_name(), arm64="arm_64bit=1\n" if self.platform.arch == "arm64" else "",
            kernel="vmlinuz-" + version, initrd="initrd.img-" + version, custom=custom + "\n" if custom else ""))
        extra = " ".join(check_lines(self.opts.cmdline, "cmdline.txt").split())
        (fw / "cmdline.txt").write_text(
            "console=tty0 console=ttyS1,115200 root=LABEL={} rw fsck.repair=yes net.ifnames=0 rootwait{}\n".format(
                LABEL_ROOT, " " + extra if extra else ""))

    # The image file -----------------------------------------------------------------------------
    def image_path(self):
        from disco.core.isobuild import BuildOptions, iso_filename
        name = self.opts.name or iso_filename(BuildOptions.from_project(self.project).iso_name, self.project)
        name = re.sub(r"\.iso$", "", name)
        if not name.endswith(".img"):
            name += ".img"
        return self.project.output / name

    def assemble(self, target):
        """Write the image with sfdisk, mkfs.vfat + mtools, mkfs.ext4 -d and dd."""
        r = self.rootfs
        runner.require("sfdisk", "mkfs.vfat", "mcopy", "mkfs.ext4")
        check_released(r)
        work = self.project.cache / "img"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        fw_stage = work / "firmware"
        fw = r / FIRMWARE
        shutil.move(str(fw), str(fw_stage))          # the boot partition is not part of the system partition
        fw.mkdir(parents=True)
        try:
            if self.opts.sysconf and not (fw_stage / "sysconf.txt").exists():
                (fw_stage / "sysconf.txt").write_text(SYSCONF)
            self.stage("Making the system partition (ext4)")
            size, files = _tree(r)
            root_mb = max(int(self.opts.size_mb or 0) - START_MB - int(self.opts.boot_mb) - 1,
                          int(size * 1.15 / 2 ** 20) + 400, 1024)
            inodes = max(files + files // 3 + 20000, 65536)
            root_img = work / "root.ext4"
            runner.run(["mkfs.ext4", "-F", "-q", "-L", LABEL_ROOT, "-N", str(inodes), "-m", "1", "-d", str(r),
                        str(root_img), "{}M".format(root_mb)])
            self.progress(60)
            self.stage("Making the boot partition (FAT32)")
            boot_img = work / "boot.vfat"
            boot_mb = int(self.opts.boot_mb)
            runner.run(["mkfs.vfat", "-F", "32", "-n", LABEL_BOOT, "-C", str(boot_img), str(boot_mb * 1024)],
                       quiet=True)
            env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
            for entry in sorted(fw_stage.iterdir()):
                runner.run(["mcopy", "-s", "-p", "-Q", "-i", str(boot_img), str(entry), "::/"], env=env, quiet=True)
            self.progress(70)
        finally:
            shutil.rmtree(fw)
            shutil.move(str(fw_stage), str(fw))
        self.stage("Writing the partition table and the partitions (sfdisk, dd)")
        total_mb = START_MB + boot_mb + root_mb + 1
        if target.exists():
            target.unlink()
        with open(target, "wb") as fh:
            fh.truncate(total_mb * 2 ** 20)
        boot_start = START_MB * 2048
        root_start = (START_MB + boot_mb) * 2048
        table = ("label: dos\nlabel-id: 0x{}\nunit: sectors\n\n"
                 "start={}, size={}, type=c, bootable\nstart={}, size={}, type=83\n").format(
            uuid.uuid4().hex[:8], boot_start, boot_mb * 2048, root_start, root_mb * 2048)
        runner.run(["sfdisk", "--no-reread", "--no-tell-kernel", "-q", str(target)], input=table, quiet=True)
        for src, start_mb in ((boot_img, START_MB), (root_img, START_MB + boot_mb)):
            runner.run(["dd", "if={}".format(src), "of={}".format(target), "bs=4M", "seek={}".format(start_mb * 2 ** 20),
                        "oflag=seek_bytes", "conv=notrunc,sparse", "status=none"])
        shutil.rmtree(work, ignore_errors=True)
        self.progress(85)
        log.info("Image %s: %d MiB (boot %d MiB, system %d MiB)", target.name, total_mb, boot_mb, root_mb)
        return target

    def compress(self, target):
        if self.opts.compress != "xz" or not runner.which("xz"):
            return target
        self.stage("Compressing the image (xz)")
        out = target.with_name(target.name + ".xz")
        if out.exists():
            out.unlink()
        from disco.core import resources
        plan = resources.plan(self.project.state.get("build", {}).get("resources") or "balanced", "xz", 0)
        runner.run(resources.wrap(["xz", "-T{}".format(plan["processors"]), "-6", "--keep", str(target)], plan))
        target.unlink()
        return out

    def checksum(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(4 << 20), b""):
                h.update(block)
        Path(str(path) + ".sha256").write_text("{}  {}\n".format(h.hexdigest(), path.name))
        return h.hexdigest()

    # Driver ---------------------------------------------------------------------------------------
    def run(self):
        p = self.project
        started = time.time()
        if self.platform.output != "img":
            raise RuntimeError("{} is made as an ISO, not as an SD-card image".format(self.platform.name))
        if not p.has_rootfs():
            raise RuntimeError("The project has no system yet: build the base first")
        from disco.core.preview import Preview
        if Preview(p).active:
            raise RuntimeError("A preview is on: keep it or throw it away before building")
        with self.chroot:
            self.ensure_packages()
            self.stage("Setting up the board (fstab, raspi-firmware, first start)")
            self.configure()
            self.default_user()
            self.initramfs()
            self.firmware()
        self.progress(30)
        self.stage("Cleaning the system")
        opts = dict(p.state.get("build", {}).get("cleanup") or cleanup.defaults())
        opts.update({"machine_id": True, "ssh_keys": True})   # every card makes its own at the first start
        cleanup.run(p, opts)
        self.progress(40)
        target = self.assemble(self.image_path())
        final = self.compress(target)
        self.stage("Writing the checksum")
        self.checksum(final)
        p.state["last_image"] = str(final)
        p.state.setdefault("board", {}).update(self.opts.to_dict())
        p.save()
        p.record("image", final.name)
        self.progress(100)
        log.info("SD-card image ready in %.0f s: %s", time.time() - started, final)
        return final


def _tree(root):
    """(bytes, number of entries) of a root filesystem, one file system only."""
    total, count, seen = 0, 0, set()
    dev = os.lstat(root).st_dev
    for top, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if os.lstat(os.path.join(top, d)).st_dev == dev]
        count += len(dirs) + len(files)
        for name in files:
            try:
                st = os.lstat(os.path.join(top, name))
            except OSError:
                continue
            if (st.st_dev, st.st_ino) in seen:
                continue
            seen.add((st.st_dev, st.st_ino))
            total += st.st_blocks * 512 if st.st_blocks else st.st_size
    return total, count


def build(project, opts=None, progress=None, stage=None):
    return ImageBuilder(project, opts, progress, stage).run()


def flash_command(image, device="/dev/sdX"):
    """How to write the image to an SD card (shown in the GUI and the guide)."""
    image = Path(image)
    if image.suffix == ".xz":
        return "xzcat {} | sudo dd of={} bs=4M status=progress conv=fsync".format(image.name, device)
    return "sudo dd if={} of={} bs=4M status=progress conv=fsync".format(image.name, device)


def kernel_files(project):
    """(vmlinuz, initrd) of the newest kernel of the image, for a test in QEMU."""
    ks = cleanup.kernels(project.rootfs)
    if not ks:
        return None, None
    v = ks[-1]
    initrd = Path(project.rootfs, "boot", "initrd.img-" + v)
    return Path(project.rootfs, "boot", "vmlinuz-" + v), (initrd if initrd.exists() else None)


def uncompressed(image, cache):
    """The raw .img of *image* (decompressed into the cache when it is .img.xz)."""
    image = Path(image)
    if image.suffix != ".xz":
        return image
    raw = Path(cache) / image.name[:-3]
    if not raw.exists() or raw.stat().st_mtime < image.stat().st_mtime:
        # Into a temporary file first: a stopped or failed run never leaves half an image that
        # would look complete the next time.
        Path(cache).mkdir(parents=True, exist_ok=True)
        tmp = raw.with_name(raw.name + ".part")
        try:
            with open(tmp, "wb") as out:
                subprocess.run(["xz", "-dc", str(image)], stdout=out, check=True)
            os.replace(tmp, raw)
        finally:
            if tmp.exists():
                tmp.unlink()
    return raw
