"""Edit the boot menu files of the ISO directly.

Files are the GRUB and ISOLINUX configuration files of the ISO tree plus
the .cfg files inside the EFI image (boot/grub/efi.img), addressed as
"efi.img:EFI/boot/grub.cfg". A saved file becomes an *override*: it is kept
in PROJECT/boot-overrides and copied over the generated boot menu at every
build, so regenerating the menu never loses a manual edit. The first
version of each file is kept in PROJECT/boot-originals for "Revert".
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from eduka_customizer.core import bootloader, runner
from eduka_customizer.core.log import log

EFI_PREFIX = "efi.img:"
EFI_IMAGE = "boot/grub/efi.img"


def _mtools_env():
    env = dict(os.environ)
    env["MTOOLS_SKIP_CHECK"] = "1"
    return env


def _efi(isodir):
    img = Path(isodir) / EFI_IMAGE
    return img if img.is_file() and shutil.which("mcopy") else None


def efi_files(isodir):
    img = _efi(isodir)
    if not img:
        return []
    out = subprocess.run(["mdir", "-/", "-b", "-i", str(img), "::/"], capture_output=True, text=True,
                         env=_mtools_env()).stdout
    files = []
    for path in out.split():
        rel = path.split("::", 1)[-1].lstrip("/")
        if rel.lower().endswith(".cfg"):
            files.append(EFI_PREFIX + rel)
    return sorted(files)


def files(project):
    """All editable boot files, relative to the ISO tree."""
    iso = project.isodir
    return [str(f.relative_to(iso)) for f in bootloader.config_files(iso)] + efi_files(iso)


def _check_key(key):
    rel = key[len(EFI_PREFIX):] if key.startswith(EFI_PREFIX) else key
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        raise ValueError("Invalid boot file: {}".format(key))
    return rel


def read(project, key):
    rel = _check_key(key)
    if key.startswith(EFI_PREFIX):
        img = _efi(project.isodir)
        if not img:
            raise FileNotFoundError("The ISO has no EFI image (or mtools is missing)")
        res = subprocess.run(["mcopy", "-n", "-i", str(img), "::/" + rel, "-"], capture_output=True,
                             env=_mtools_env())
        if res.returncode:
            raise FileNotFoundError(res.stderr.decode(errors="replace").strip() or rel)
        return res.stdout.decode("utf-8", "replace")
    return (project.isodir / rel).read_text(errors="replace")


def _write(project, key, text):
    rel = _check_key(key)
    if key.startswith(EFI_PREFIX):
        img = _efi(project.isodir)
        if not img:
            raise FileNotFoundError("The ISO has no EFI image (or mtools is missing)")
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".cfg") as fh:
            fh.write(text)
        try:
            runner.run(["mcopy", "-o", "-i", img, fh.name, "::/" + rel], env=_mtools_env(), quiet=True)
        finally:
            os.unlink(fh.name)
    else:
        target = project.isodir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


def _store(project, folder, key):
    return project.path / folder / key.replace(":", "/")


def validate(project, key, text):
    """Return a list of problems found in *text* (empty when it looks fine)."""
    problems = []
    rel = _check_key(key)
    is_grub = key.startswith(EFI_PREFIX) or Path(rel).parent.name not in ("isolinux", "syslinux")
    if is_grub:
        checker = shutil.which("grub-script-check")
        if checker:
            res = subprocess.run([checker], input=text, capture_output=True, text=True)
            if res.returncode:
                problems.append("GRUB syntax: " + (res.stderr or res.stdout).strip())
        if text.count("{") != text.count("}"):
            problems.append("The numbers of '{' and '}' differ")
        paths = re.findall(r"(?m)^\s*(?:linux|linuxefi|initrd|initrdefi)\s+(\S+)", text)
    else:
        paths = re.findall(r"(?im)^\s*(?:kernel|linux|initrd)\s+(\S+)", text)
        paths += re.findall(r"(?i)initrd=(\S+)", text)
        for inc in re.findall(r"(?im)^\s*include\s+(\S+)", text):
            base = project.isodir / Path(rel).parent
            if not ((base / inc).exists() or (project.isodir / inc.lstrip("/")).exists()):
                problems.append("Included file not found: " + inc)
    for p in paths:
        if "$" in p or p.startswith("("):
            continue
        for candidate in p.split(","):
            if candidate and not (project.isodir / candidate.lstrip("/")).exists() \
                    and not candidate.startswith("/live/"):
                problems.append("File not found in the ISO: " + candidate)
    live = project.isodir / "live"
    if re.search(r"/live/vmlinuz\b", text) and live.is_dir() and not (live / "vmlinuz").exists() \
            and not list(live.glob("vmlinuz*")):
        problems.append("/live/vmlinuz is not in the ISO yet (it is copied there by the build)")
    return problems


def save(project, key, text, keep=True):
    """Write *text* now and (with keep) re-apply it after every boot menu regeneration."""
    current = None
    try:
        current = read(project, key)
    except (OSError, FileNotFoundError):
        pass
    original = _store(project, "boot-originals", key)
    if current is not None and not original.exists():
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text(current)
    _write(project, key, text)
    overrides = project.state.setdefault("boot", {}).setdefault("overrides", [])
    if keep:
        o = _store(project, "boot-overrides", key)
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text(text)
        if key not in overrides:
            overrides.append(key)
    elif key in overrides:
        overrides.remove(key)
        _store(project, "boot-overrides", key).unlink(missing_ok=True)
    project.save()
    project.record("edit-boot-file", key)


def revert(project, key):
    """Forget the manual edit and restore the file as it was before the first edit."""
    original = _store(project, "boot-originals", key)
    if original.exists():
        _write(project, key, original.read_text())
    overrides = project.state.setdefault("boot", {}).setdefault("overrides", [])
    if key in overrides:
        overrides.remove(key)
    _store(project, "boot-overrides", key).unlink(missing_ok=True)
    project.save()
    project.record("revert-boot-file", key)


def edited(project, key):
    """True once the file was saved from the editor (its original is kept)."""
    return _store(project, "boot-originals", key).exists()


def overrides(project):
    return list(project.state.get("boot", {}).get("overrides", []))


def apply_overrides(project):
    """Copy every kept manual edit over the boot menu (called by the build)."""
    applied = 0
    for key in overrides(project):
        o = _store(project, "boot-overrides", key)
        if not o.exists():
            continue
        try:
            _write(project, key, o.read_text())
            applied += 1
        except (OSError, FileNotFoundError, RuntimeError) as e:
            log.warning("Could not apply the edited boot file %s: %s", key, e)
    if applied:
        log.info("Applied %d edited boot file(s)", applied)
    return applied
