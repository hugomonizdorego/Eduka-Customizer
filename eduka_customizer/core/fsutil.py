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


ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tar.zst")


def is_archive(path):
    return str(path).lower().endswith(ARCHIVE_SUFFIXES)


def link_stays_inside(name, linkname):
    """True when a symbolic link inside an archive points to a place inside it.

    Icon themes are full of relative links (../apps/x.svg, 64x64 -> ../Papirus/64x64);
    only absolute links and links that climb out of the archive are refused.
    """
    import posixpath
    if linkname.startswith("/"):
        return False
    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), linkname))
    return not (target == ".." or target.startswith("../"))


def extract_archive(source, dest):
    """Extract a .zip or .tar.* archive, refusing absolute paths, '..', devices and
    links that point outside the archive."""
    import tarfile
    import zipfile
    from pathlib import Path
    source, dest = Path(source), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as zf:
            for name in zf.namelist():
                if name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError("Unsafe path in archive: {}".format(name))
            zf.extractall(dest)
        return dest
    if tarfile.is_tarfile(source):
        with tarfile.open(source) as tf:
            for m in tf.getmembers():
                if m.name.startswith("/") or ".." in Path(m.name).parts or m.isdev() or m.islnk():
                    raise ValueError("Unsafe entry in archive: {}".format(m.name))
                if m.issym() and not link_stays_inside(m.name, m.linkname):
                    raise ValueError("Unsafe link in archive: {}".format(m.name))
            try:
                tf.extractall(dest, filter="data")
            except TypeError:  # Python < 3.11.4
                tf.extractall(dest)
        return dest
    raise ValueError("Not a supported archive: {}".format(source.name))
