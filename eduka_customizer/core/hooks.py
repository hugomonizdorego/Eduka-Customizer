"""Run user scripts (hooks) and one-off commands inside the image."""

import shlex
import shutil
import stat
from pathlib import Path

from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log


def run_hook(project, script, args=()):
    """Copy *script* into the image and execute it as root inside the chroot."""
    script = Path(script)
    if not script.is_file():
        raise FileNotFoundError(script)
    tmp = project.rootfs / "tmp/eduka-hooks"
    tmp.mkdir(parents=True, exist_ok=True)
    target = tmp / script.name
    shutil.copy2(script, target)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    log.info("Running hook %s", script.name)
    try:
        Chroot(project.rootfs).run(["/tmp/eduka-hooks/" + script.name] + list(args))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    project.mark_initramfs_dirty()
    project.record("hook", script.name)


def run_command(project, command):
    """Run a shell command line inside the image (non-interactive)."""
    if not command.strip():
        return
    log.info("chroot$ %s", command)
    Chroot(project.rootfs).run(["/bin/bash", "-lc", command])
    project.mark_initramfs_dirty()
    project.record("command", command)


def hook_dirs(project):
    """Hooks in <project>/hooks run in order with 'eduka-customizer hooks'."""
    d = project.path / "hooks"
    d.mkdir(exist_ok=True)
    return sorted(p for p in d.iterdir() if p.is_file() and not p.name.startswith("."))


def quote(args):
    return " ".join(shlex.quote(a) for a in args)
