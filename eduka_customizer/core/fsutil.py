"""File system helpers."""

import os
import shutil
import stat

from eduka_customizer.core.log import log


def copy_regular(src, dst, *, follow_symlinks=True):
    """copy2 that skips device nodes, FIFOs and sockets.

    Reading a device node (for example one planted in a Rock Ridge ISO or a
    theme archive) could copy a host disk or never end (/dev/zero).
    """
    st = os.stat(src) if follow_symlinks else os.lstat(src)
    if not stat.S_ISREG(st.st_mode):
        log.warning("Skipping special file %s", src)
        return dst
    return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)


def copytree(src, dst, **kw):
    """shutil.copytree that keeps symlinks and never reads special files."""
    kw.setdefault("symlinks", True)
    return shutil.copytree(src, dst, copy_function=copy_regular, **kw)
