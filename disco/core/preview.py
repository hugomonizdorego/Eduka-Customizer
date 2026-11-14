"""Try the waiting changes before applying them.

The project folder gets an overlay file system on top of itself: everything the
changes write (packages, settings, project.json) lands in a separate folder next
to the project, while the project itself stays untouched. Start the live session
to look at the result; then either keep the changes (they are applied for real)
or throw the preview away. Nothing of the preview is left behind either way.
"""

import shutil
from pathlib import Path

from disco.core import runner
from disco.core.log import log


class Preview:
    def __init__(self, project):
        self.project = project
        self.path = Path(project.path).resolve()
        self.work = self.path.parent / ".{}.preview".format(self.path.name)

    def mounted(self):
        """True when the preview's overlay is on the project folder (and not a disk that the
        project folder is the mount point of)."""
        from disco.core.chroot import mount_type
        return mount_type(self.path) == "overlay"

    @property
    def active(self):
        return self.mounted() and self.work.is_dir()

    def start(self):
        """Put the overlay on the project. Everything written from now on is temporary."""
        from disco.core.chroot import Chroot, mounts_under, unmount_all
        if self.active:
            return
        if any(c in str(self.path) for c in ",:"):
            raise RuntimeError("A preview cannot be put on a folder whose path has a comma or a colon ({}): "
                               "move the project to a simpler folder name".format(self.path))
        Chroot(self.project.rootfs).force_release()
        unmount_all(self.path, include_self=False)
        if mounts_under(self.path, include_self=False):
            raise RuntimeError("Something is still mounted in the project: {}".format(", ".join(
                mounts_under(self.path, include_self=False))))
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
        from disco.core.preflight import tree_size
        return tree_size(self.work / "upper") if self.work.exists() else 0

    def stop(self):
        """Throw the preview away: the project is as before."""
        from disco.core.chroot import Chroot, mounts_under, unmount_all
        Chroot(self.project.rootfs).force_release()
        if self.mounted():
            for mp in sorted(set(mounts_under(self.path, include_self=False)), key=len, reverse=True):
                runner.run(["umount", "-l", mp], check=False, quiet=True, cancellable=False)
            try:
                runner.run(["umount", str(self.path)], quiet=True, cancellable=False)
            except runner.CommandError:
                runner.run(["umount", "-l", str(self.path)], quiet=True, cancellable=False)
        unmount_all(self.path / "rootfs")
        if self.mounted():
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
    if p.mounted() or p.work.exists():
        p.stop()
        return True
    return False
