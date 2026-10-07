"""Inspect and extract Debian live ISO images.

Boot parameters of the source image are recorded with
``xorriso -report_el_torito as_mkisofs`` (the same technique Cubic uses)
so the rebuilt image boots exactly like the original on BIOS and UEFI.
"""

import json
import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path

from eduka_customizer.core import distro, runner
from eduka_customizer.core import fsutil
from eduka_customizer.core.log import log

SQUASHFS_CANDIDATES = ("live/filesystem.squashfs",)
UNIT_BYTES = {"": 1, "b": 1, "d": 512, "s": 2048, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
_INTERVAL = re.compile(r"^--interval:local_fs:(\d+)([a-z]?)-(\d+)([a-z]?):([^:]*):(.+)$")


class InvalidISO(ValueError):
    pass


def iso_volume_id(iso):
    out = runner.output(["xorriso", "-indev", iso, "-pvd_info"], check=False)
    for line in out.splitlines():
        if line.startswith("Volume Id"):
            return line.split(":", 1)[1].strip()
    return ""


def list_root(iso):
    out = runner.output(["xorriso", "-indev", iso, "-ls", "/"], check=False)
    return [line.strip().strip("'") for line in out.splitlines() if line.strip().startswith("'")]


def inspect(iso):
    """Validate the ISO layout before spending time extracting it."""
    iso = str(iso)
    if not os.path.isfile(iso):
        raise InvalidISO("ISO file not found: {}".format(iso))
    entries = [e.lstrip("/").lower() for e in list_root(iso)]
    if "casper" in entries:
        raise InvalidISO("This is an Ubuntu (casper) image. Ubuntu and its derivatives are not "
                         "supported - use a Debian or Edukasaun OS live ISO.")
    if "live" not in entries:
        raise InvalidISO("No /live directory: this is not a Debian live image. Use a Debian live "
                         "ISO (debian-live-*.iso) or an Edukasaun OS ISO, or bootstrap a new base.")
    return {"volume_id": iso_volume_id(iso), "entries": entries}


def report_boot(iso):
    """Return the mkisofs options needed to reproduce the source boot setup."""
    out = runner.output(["xorriso", "-indev", iso, "-report_el_torito", "as_mkisofs"], check=False)
    args = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith(("xorriso", "Drive current", "Media current",
                                        "Media status", "Media summary", "Boot record",
                                        "Volume id", "libisofs", "Drive type")):
            continue
        try:
            args.extend(shlex.split(line))
        except ValueError:
            log.warning("Could not parse boot report line: %s", line)
    return args


def _to_bytes(num, unit):
    return int(num) * UNIT_BYTES[unit]


def detach_boot_args(args, iso, dest_dir):
    """Copy every '--interval:local_fs' range of the source ISO into files.

    After this the rebuild no longer needs the original ISO on disk.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = []
    n = 0
    for arg in args:
        m = _INTERVAL.match(arg)
        if not m:
            result.append(arg)
            continue
        start, sunit, end, eunit, flags, path = m.groups()
        path = path.strip("'")
        if os.path.realpath(path) != os.path.realpath(str(iso)) and os.path.exists(path):
            result.append(arg)
            continue
        start_b = _to_bytes(start, sunit)
        # Interval ends are inclusive: the end block is part of the range.
        end_b = _to_bytes(int(end) + 1, eunit) - 1
        length = end_b - start_b + 1
        n += 1
        out = dest_dir / "boot-interval-{}.img".format(n)
        with open(iso, "rb") as src, open(out, "wb") as dst:
            src.seek(start_b)
            remaining = length
            while remaining > 0:
                chunk = src.read(min(remaining, 1 << 20))
                if not chunk:
                    break
                dst.write(chunk)
                remaining -= len(chunk)
        result.append("--interval:local_fs:0-{}:{}:{}".format(length - 1, flags, out))
    return result


def strip_output_args(args):
    """Remove options we always set ourselves (volume id, dates, output)."""
    out = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("-V", "-volid", "-o", "-outdev"):
            skip_next = True
            continue
        if arg.startswith("--modification-date=") or arg == "-as" or arg == "mkisofs":
            continue
        out.append(arg)
    return out


def _mount(iso, mnt):
    try:
        runner.run(["modprobe", "-q", "loop"], quiet=True, check=False)
    except FileNotFoundError:
        pass
    runner.run(["mount", "-o", "loop,ro", "-t", "iso9660", iso, mnt], quiet=True)


def extract(project, iso, progress=None):
    """Extract *iso* into the project's iso/ and rootfs/ trees."""
    runner.require("xorriso", "unsquashfs")
    iso = str(Path(iso).resolve())
    layout = inspect(iso)
    log.info("Source image: %s (%s)", iso, layout["volume_id"] or "no label")

    from eduka_customizer.core.chroot import Chroot, safe_rmtree
    if project.rootfs.exists():
        Chroot(project.rootfs).force_release()
    for d in (project.isodir, project.rootfs):
        if d.exists() and any(d.iterdir()):
            log.info("Removing old %s", d)
            safe_rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    mnt = Path(tempfile.mkdtemp(prefix="eduka-iso-", dir=str(project.cache)))
    mounted = False
    try:
        try:
            _mount(iso, mnt)
            mounted = True
            src_root = mnt
        except (runner.CommandError, FileNotFoundError):
            log.warning("Loop mount unavailable, extracting with xorriso instead")
            runner.run(["xorriso", "-osirrox", "on", "-indev", iso, "-extract", "/", mnt])
            src_root = mnt

        squash = None
        for rel in SQUASHFS_CANDIDATES:
            if (src_root / rel).is_file():
                squash = src_root / rel
                break
        if not squash:
            raise InvalidISO("live/filesystem.squashfs not found in the image")

        log.info("Copying ISO boot files")
        for item in src_root.iterdir():
            dest = project.isodir / item.name
            if item.is_dir():
                fsutil.copytree(item, dest, symlinks=True,
                                ignore=lambda d, names: [n for n in names
                                                         if os.path.join(d, n) == str(squash)])
            else:
                fsutil.copy_regular(item, dest)
        runner.run(["chmod", "-R", "u+w", project.isodir], quiet=True)

        log.info("Unpacking the root filesystem (this takes a while)")
        runner.run(["unsquashfs", "-f", "-d", project.rootfs, squash], progress=progress)
    finally:
        if mounted:
            runner.run(["umount", "-l", mnt], quiet=True, check=False)
        shutil.rmtree(mnt, ignore_errors=True)

    info = distro.detect(project.rootfs)
    distro.validate(info, project.rootfs)
    log.info("Detected %s", info.summary())

    log.info("Recording boot configuration of the source image")
    args = strip_output_args(report_boot(iso))
    if args:
        args = detach_boot_args(args, iso, project.bootdir)
    (project.bootdir / "replay.json").write_text(json.dumps(args, indent=1))

    project.state["source"].update({"kind": "iso", "path": iso, "label": info.pretty_name,
                                    "volume_id": layout["volume_id"],
                                    "boot_mode": "replay" if args else "generate"})
    project.state["distro"] = info.to_dict()
    project.record("extract", iso)
    return info


def load_replay(project):
    p = project.bootdir / "replay.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return []
