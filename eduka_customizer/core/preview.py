"""Try the waiting changes before applying them.

The project folder gets an overlay file system on top of itself: everything the
changes write (packages, settings, project.json) lands in a separate folder next
to the project, while the project itself stays untouched. Start the live session
to look at the result; then either keep the changes (they are applied for real)
or throw the preview away. Nothing of the preview is left behind either way.
"""

import os
import shutil
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.log import log


class Preview:
    def __init__(self, project):
        self.project = project
        self.path = Path(project.path).resolve()
        self.work = self.path.parent / ".{}.preview".format(self.path.name)

    @property
    def active(self):
        return os.path.ismount(self.path) and self.work.is_dir()

    def start(self):
        """Put the overlay on the project. Everything written from now on is temporary."""
        from eduka_customizer.core.chroot import Chroot, mounts_under, unmount_all
        if self.active:
            return
        Chroot(self.project.rootfs).force_release()
        unmount_all(self.path)
        if mounts_under(self.path):
            raise RuntimeError("Something is still mounted in the project: {}".format(", ".join(
                mounts_under(self.path))))
        if self.work.exists():
            shutil.rmtree(self.work)
        upper, work = self.work / "upper", self.work / "work"
        upper.mkdir(parents=True)
        work.mkdir()
        try:
            runner.run(["mount", "-t", "overlay", "overlay", "-o",
                        "lowerdir={},upperdir={},workdir={}".format(self.path, upper, work), self.path])
        except runner.CommandError as e:
            shutil.rmtree(self.work, ignore_errors=True)
            raise RuntimeError("A preview needs overlayfs, which this computer could not mount: {}".format(e))
        log.info("Preview started: changes go to %s until the preview ends", upper)

    def size(self):
        """Bytes the preview has written so far."""
        from eduka_customizer.core.preflight import tree_size
        return tree_size(self.work / "upper") if self.work.exists() else 0

    def stop(self):
        """Throw the preview away: the project is as before."""
        from eduka_customizer.core.chroot import Chroot, mounts_under, unmount_all
        Chroot(self.project.rootfs).force_release()
        if os.path.ismount(self.path):
            for mp in sorted(set(mounts_under(self.path)) - {str(self.path)}, key=len, reverse=True):
                runner.run(["umount", "-l", mp], check=False, quiet=True)
            try:
                runner.run(["umount", str(self.path)], quiet=True)
            except runner.CommandError:
                runner.run(["umount", "-l", str(self.path)], quiet=True)
        unmount_all(self.path / "rootfs")
        if os.path.ismount(self.path):
            raise RuntimeError("The preview could not be unmounted; close programs that use the project")
        shutil.rmtree(self.work, ignore_errors=True)
        try:
            self.project.load()  # the state from before the preview
        except (OSError, ValueError):
            pass
        log.info("Preview ended; the project is as it was")


def leftover(project):
    """A preview left behind by a crash (mounted or not): end it."""
    p = Preview(project)
    if os.path.ismount(p.path) or p.work.exists():
        p.stop()
        return True
    return False
