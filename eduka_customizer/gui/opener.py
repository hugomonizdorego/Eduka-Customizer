"""Open web pages, files and folders in the user's own programs.

DistroForge runs as root (pkexec or sudo). A browser or file manager must not run
as root, so they are started as the person who started DistroForge with
runuser. runuser lives in /usr/sbin, which is not in every PATH: every program is
looked up with its full path, and when something is missing the Qt way is tried.
"""

import os
import pwd
import shutil
import subprocess

from eduka_customizer.core.log import log

SEARCH_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def which(name):
    """Full path of *name*, also in the sbin folders; None when missing."""
    return shutil.which(name, path=os.environ.get("PATH", "") + ":" + SEARCH_PATH)


def real_user():
    """The person who started the program (pkexec or sudo), or None."""
    uid = os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID")
    if uid and uid.isdigit():
        try:
            return pwd.getpwuid(int(uid)).pw_name
        except KeyError:
            return None
    return None


def user_command(user, argv):
    """argv run as *user* (runuser, setpriv or sudo), or None."""
    runuser = which("runuser")
    if runuser:
        return [runuser, "-u", user, "--"] + argv
    sudo = which("sudo")
    if sudo:
        return [sudo, "-u", user, "--"] + argv
    return None


def user_env(user):
    pw = pwd.getpwnam(user)
    env = {k: v for k, v in os.environ.items() if k in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
                                                        "XAUTHORITY", "LANG", "LC_ALL", "DBUS_SESSION_BUS_ADDRESS",
                                                        "XDG_CURRENT_DESKTOP", "DESKTOP_SESSION")}
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/{}".format(pw.pw_uid))
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/{}/bus".format(pw.pw_uid))
    env["HOME"] = pw.pw_dir
    env["USER"] = env["LOGNAME"] = user
    env["PATH"] = SEARCH_PATH
    return env


def open_url(target):
    """Open a URL, file or folder. Returns True when a program was started."""
    target = str(target)
    xdg = which("xdg-open")
    user = real_user()
    if os.geteuid() == 0 and user and xdg:
        cmd = user_command(user, [xdg, target])
        if cmd:
            try:
                subprocess.Popen(cmd, env=user_env(user), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                return True
            except OSError as e:
                log.warning("Could not open %s as %s: %s", target, user, e)
    try:
        from eduka_customizer.qt.core import QUrl
        from eduka_customizer.qt.gui import QDesktopServices
        url = QUrl(target) if "://" in target else QUrl.fromLocalFile(target)
        if QDesktopServices.openUrl(url):
            return True
    except Exception as e:  # no GUI (tests) or no handler
        log.debug("Qt could not open %s: %s", target, e)
    if xdg:
        try:
            subprocess.Popen([xdg, target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
        except OSError as e:
            log.warning("Could not open %s: %s", target, e)
    log.warning("No program to open %s", target)
    return False
