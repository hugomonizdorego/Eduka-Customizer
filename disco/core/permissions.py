"""Folders of a project that belong to you: change them without administrator rights.

D!sco runs as administrator (root). The folders you change by hand belong to you,
the person who started D!sco, so your own file manager and editor can open,
add, change and delete everything in them:

  overlay   files copied into the system as they are (overlay/etc/skel/... -> /etc/skel/...)
  hooks     your scripts, run inside the system
  debs      your own .deb packages
  branding  your pictures and documents
  lists     package lists
  iso       the files around the system on the ISO (boot menus, splash pictures)
  output    the finished ISO and SD-card images

The system folder (rootfs) is different: its owners and permissions go into the
ISO exactly as they are. A system where everyone may change every file is unsafe
and does not even start correctly (sudo and SSH refuse to work, for example). Edit
it in D!sco (Files step, as administrator), or put your files into overlay: they
are copied into the system with the right owner (root) when the system is built.
"""

import os
import pwd
from pathlib import Path

from disco.core.log import log

USER_FOLDERS = ["overlay", "hooks", "debs", "branding", "lists", "iso", "output"]


def real_user():
    """(uid, gid, name) of the person who started D!sco through pkexec or sudo, or None."""
    uid = os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID")
    if not uid or not uid.isdigit() or int(uid) == 0:
        return None
    try:
        pw = pwd.getpwuid(int(uid))
    except KeyError:
        return None
    return pw.pw_uid, pw.pw_gid, pw.pw_name


def give_to_user(path, user=None):
    """Make *path* (and everything below it) belong to the real user, readable and writable by them."""
    user = user or real_user()
    path = Path(path)
    if user is None or os.geteuid() != 0 or not path.exists():
        return 0
    uid, gid = user[0], user[1]
    count = 0
    items = [path]
    if path.is_dir() and not path.is_symlink():
        # os.walk does not follow links into other folders (a link in the folder may lead anywhere).
        for top, dirs, files in os.walk(str(path), followlinks=False):
            items += [Path(top, n) for n in dirs + files]
    for p in items:
        try:
            os.lchown(p, uid, gid)
            if not p.is_symlink():
                mode = p.stat().st_mode
                p.chmod(mode | 0o600 | (0o100 if p.is_dir() else 0))   # read and write; folders can be opened
            count += 1
        except OSError as e:
            log.debug("Could not hand %s over: %s", p, e)
    return count


def share_user_folders(project, user=None):
    """Create the user folders of a project and give them to the real user. Returns their paths."""
    out = []
    for name in USER_FOLDERS:
        d = Path(project.path) / name
        d.mkdir(parents=True, exist_ok=True)
        give_to_user(d, user)
        out.append(d)
    # The project folder itself can be opened (but project.json and rootfs stay root's).
    user = user or real_user()
    if user and os.geteuid() == 0:
        try:
            st = Path(project.path).stat()
            Path(project.path).chmod(st.st_mode | 0o055)
        except OSError:
            pass
    return out
