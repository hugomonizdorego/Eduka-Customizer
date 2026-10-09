"""The folders of a project, and cleaning up after the build.

Everything of a project lives in one folder, in separate sub-folders that you
may also open and change by hand. When the ISO is finished, everything but the
ISO can be deleted: the build folders are big (the whole system, twice).
"""

import os
import shutil
from pathlib import Path

from eduka_customizer.core.log import log

# (folder, what it holds, safe to change by hand)
FOLDERS = [
    ("rootfs", "The system of your distribution, as it will be installed. Change files here by hand if you like "
               "(as root); packages are better changed in DistroForge.", True),
    ("iso", "The files of the ISO around the system: boot menus (boot/grub, isolinux), the EFI image and "
            "live/filesystem.squashfs after a build.", True),
    ("hooks", "Your own scripts: every *.sh here runs inside the system (Advanced → Terminal & Live).", True),
    ("workshop", "Debian packages opened in the Package Workshop.", True),
    ("branding", "The source of your <id>-branding package (Identity & Branding).", True),
    ("boot", "Boot files made by the build (kernel, initrd, EFI image).", False),
    ("cache", "Downloads and temporary files. Safe to delete.", False),
    ("logs", "What DistroForge did in this project (distroforge.log, qemu.log, ...).", False),
    ("output", "The finished ISO images and their checksums.", False),
]
README = "README.txt"
CHECKSUMS = (".sha256", ".sha512", ".md5")
# Everything DistroForge itself puts in a project folder. Other files are never deleted.
KNOWN = {name for name, _t, _h in FOLDERS} | {"downloads", "workshop-debs", "boot-originals", "boot-overrides",
                                             "recipe-wizard.json", "project.json", "project.tmp", ".lock",
                                             README}


def write_readme(project):
    """A README.txt in the project folder that says what each folder is for."""
    lines = ["This is a DistroForge project folder. Every part has its own folder:", ""]
    for name, text, by_hand in FOLDERS:
        lines.append("{:10} {}{}".format(name + "/", text, "" if by_hand else " (made by DistroForge)"))
    lines += ["", "project.json  the settings of the project (do not edit while DistroForge is open).",
              "", "Open the project again with: distroforge gui " + str(project.path)]
    p = Path(project.path) / README
    try:
        p.write_text("\n".join(lines) + "\n")
    except OSError as e:
        log.debug("Could not write %s: %s", p, e)


def folder_sizes(project):
    """[(name, path, bytes)] of the folders that exist."""
    from eduka_customizer.core.preflight import tree_size
    out = []
    for name, _text, _h in FOLDERS:
        p = Path(project.path) / name
        if p.exists():
            out.append((name, p, tree_size(p)))
    return out


def iso_files(project):
    """The finished ISO images and their checksum files."""
    out = Path(project.output)
    if not out.is_dir():
        return []
    isos = sorted(out.glob("*.iso"))
    files = list(isos)
    for iso in isos:
        files += [Path(str(iso) + ext) for ext in CHECKSUMS if Path(str(iso) + ext).exists()]
    return files


def keep_only_iso(project, progress=None):
    """Delete everything of the project but the ISO images (and their checksums).

    The ISOs move to the project folder itself. Nothing is deleted while anything
    is still mounted inside the project (that could delete files of this computer).
    Only what DistroForge made is deleted; files of your own in the folder stay.
    Returns (ISO files, names of your own files that were kept)."""
    from eduka_customizer.core.chroot import Chroot, mounts_under, unmount_all
    root = Path(project.path).resolve()
    keep = iso_files(project)
    if not [f for f in keep if f.suffix == ".iso"]:
        raise RuntimeError("There is no finished ISO in {}: nothing was deleted".format(project.output))
    if not (root / "project.json").is_file() or len(root.parts) < 3:
        raise RuntimeError("{} is not a project folder: nothing was deleted".format(root))
    Chroot(project.rootfs).force_release()
    unmount_all(root)
    left = mounts_under(root)
    if left:
        raise RuntimeError("Still mounted, nothing was deleted: {}".format(", ".join(left)))
    moved = []
    for f in keep:
        dest = root / f.name
        if f.resolve() != dest:
            shutil.move(str(f), str(dest))
        moved.append(dest)
    keep_names = {m.name for m in moved}
    own = []
    try:
        project.unlock()
    except Exception:  # the lock may already be gone
        pass
    for entry in sorted(root.iterdir()):
        if entry.name in keep_names:
            continue
        if entry.name not in KNOWN:
            own.append(entry.name)
            continue
        if progress:
            progress("Deleting {}".format(entry.name))
        log.info("Deleting %s", entry)
        if entry.is_symlink() or not entry.is_dir():
            entry.unlink()
            continue
        # Never cross into another file system (a mount that appeared meanwhile).
        dev = entry.stat().st_dev
        for top, dirs, _files in os.walk(entry):
            for d in dirs:
                p = os.path.join(top, d)
                if not os.path.islink(p) and os.stat(p).st_dev != dev:
                    raise RuntimeError("{} is another file system: stopped".format(p))
        shutil.rmtree(entry)
    log.info("Only the ISO is left: %s", ", ".join(str(m) for m in moved))
    if own:
        log.info("Your own files stay: %s", ", ".join(own))
    return moved, own
