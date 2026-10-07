"""Safe chroot handling for the project's root filesystem.

Mounts are shared between processes (GUI, terminal shell, CLI): a small
registry of PIDs inside the project decides who mounts and who unmounts.
"""

import contextlib
import fcntl
import json
import os
import shutil
import threading
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.log import log

# (source, relative target, fstype, options)
PSEUDO_FS = [
    ("proc", "proc", "proc", "nosuid,nodev,noexec"),
    ("sysfs", "sys", "sysfs", "nosuid,nodev,noexec,ro"),
    # /dev is bind mounted recursively and made a slave so nothing mounted
    # below it inside the chroot can ever propagate back to the host.
    ("/dev", "dev", None, "rbind"),
    ("tmpfs", "run", "tmpfs", "nosuid,nodev,mode=755"),
]

# Process wide reference counts, keyed by rootfs path.
_ACTIVE = {}
_ACTIVE_LOCK = threading.Lock()

POLICY_RC = "usr/sbin/policy-rc.d"
POLICY_MARK = "# eduka-customizer: block service start inside chroot\n"


def _unescape_mount(path):
    return path.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n").replace("\\134", "\\")


def mounts_under(path):
    path = os.path.realpath(str(path))
    found = []
    try:
        with open("/proc/self/mountinfo") as fh:
            for line in fh:
                mp = _unescape_mount(line.split()[4])
                if mp == path or mp.startswith(path.rstrip("/") + "/"):
                    found.append(mp)
    except OSError:
        pass
    return found


def unmount_all(path):
    """Unmount everything below *path*, deepest first."""
    for mp in sorted(set(mounts_under(path)), key=lambda m: m.count("/"), reverse=True):
        log.info("Unmounting %s", mp)
        try:
            runner.run(["umount", mp], quiet=True)
        except runner.CommandError:
            runner.run(["umount", "-l", mp], quiet=True, check=False)


def safe_rmtree(path):
    """Delete a tree only after everything mounted inside it is gone.

    Deleting a root filesystem with /dev or /proc still bind mounted would
    delete files of the host computer.
    """
    path = Path(path)
    if not path.exists():
        return
    unmount_all(path)
    left = mounts_under(path)
    if left:
        raise RuntimeError("Refusing to delete {}: still mounted: {}".format(path, ", ".join(left)))
    shutil.rmtree(path)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Chroot:
    """Context manager preparing rootfs for running commands in it."""

    def __init__(self, rootfs, x11=False):
        self.rootfs = Path(rootfs).resolve()
        self.x11 = x11
        self.registry = self.rootfs.parent / ".chroot-users.json"
        self.lockfile = self.rootfs.parent / ".chroot.lock"

    # Registry --------------------------------------------------------
    @contextlib.contextmanager
    def _locked(self):
        with open(self.lockfile, "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _users(self):
        try:
            data = json.loads(self.registry.read_text())
        except (OSError, ValueError):
            data = []
        return [p for p in data if isinstance(p, int) and _alive(p)]

    def _write_users(self, users):
        self.registry.write_text(json.dumps(sorted(set(users))))

    # Enter/leave -----------------------------------------------------
    def __enter__(self):
        key = str(self.rootfs)
        with _ACTIVE_LOCK:
            if _ACTIVE.get(key, 0) == 0:
                if not (self.rootfs / "usr").is_dir():
                    raise RuntimeError("Root filesystem not found: {}".format(self.rootfs))
                with self._locked():
                    users = self._users()
                    if not users:
                        try:
                            self._setup()
                        except BaseException:
                            self._teardown()
                            raise
                    users.append(os.getpid())
                    self._write_users(users)
            _ACTIVE[key] = _ACTIVE.get(key, 0) + 1
        if self.x11:
            self._bind_x11()
        return self

    def __exit__(self, *exc):
        if self.x11:
            self._unbind_x11()
        key = str(self.rootfs)
        with _ACTIVE_LOCK:
            _ACTIVE[key] = _ACTIVE.get(key, 1) - 1
            if _ACTIVE[key] > 0:
                return False
            with self._locked():
                users = [p for p in self._users() if p != os.getpid()]
                self._write_users(users)
                if not users:
                    self._teardown()
        return False

    def force_release(self):
        """Recover after a crash: forget all users and unmount everything."""
        with _ACTIVE_LOCK:
            _ACTIVE.pop(str(self.rootfs), None)
            with self._locked():
                self._write_users([])
                self._teardown()

    def _setup(self):
        log.debug("Preparing chroot %s", self.rootfs)
        for source, rel, fstype, opts in PSEUDO_FS:
            target = self.rootfs / rel
            target.mkdir(parents=True, exist_ok=True)
            if os.path.ismount(target):
                continue
            if fstype is None:
                runner.run(["mount", "--" + opts, source, target], quiet=True)
                runner.run(["mount", "--make-rslave", target], quiet=True)
            else:
                runner.run(["mount", "-t", fstype, "-o", opts, source, target], quiet=True)
        self._setup_resolv()
        self._setup_policy()
        mtab = self.rootfs / "etc/mtab"
        if not mtab.exists() and not mtab.is_symlink():
            os.symlink("../proc/self/mounts", mtab)

    def _teardown(self):
        self._restore_policy()
        self._restore_resolv()
        unmount_all(self.rootfs)

    # resolv.conf -----------------------------------------------------
    def _host_resolv(self):
        for candidate in ("/run/systemd/resolve/resolv.conf", "/etc/resolv.conf"):
            try:
                text = Path(candidate).read_text()
            except OSError:
                continue
            if candidate == "/etc/resolv.conf" or "nameserver" in text:
                if "127.0.0.53" in text and candidate == "/etc/resolv.conf":
                    continue
                return text
        return "nameserver 1.1.1.1\nnameserver 9.9.9.9\n"

    def _setup_resolv(self):
        resolv = self.rootfs / "etc/resolv.conf"
        backup = self.rootfs / "etc/resolv.conf.eduka-backup"
        if backup.exists() or backup.is_symlink():
            return  # left over from a crash; keep the original backup
        if resolv.exists() or resolv.is_symlink():
            os.rename(resolv, backup)
        resolv.write_text(self._host_resolv())

    def _restore_resolv(self):
        resolv = self.rootfs / "etc/resolv.conf"
        backup = self.rootfs / "etc/resolv.conf.eduka-backup"
        if backup.exists() or backup.is_symlink():
            if resolv.exists() or resolv.is_symlink():
                resolv.unlink()
            os.rename(backup, resolv)

    # policy-rc.d -----------------------------------------------------
    def _setup_policy(self):
        policy = self.rootfs / POLICY_RC
        if policy.exists():
            return
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text("#!/bin/sh\n" + POLICY_MARK + "exit 101\n")
        policy.chmod(0o755)

    def _restore_policy(self):
        policy = self.rootfs / POLICY_RC
        try:
            if POLICY_MARK in policy.read_text():
                policy.unlink()
        except OSError:
            pass

    # X11 for nested sessions -------------------------------------------
    def _bind_x11(self):
        target = self.rootfs / "tmp/.X11-unix"
        target.mkdir(parents=True, exist_ok=True)
        if not os.path.ismount(target) and os.path.isdir("/tmp/.X11-unix"):
            runner.run(["mount", "--bind", "/tmp/.X11-unix", target], quiet=True)

    def _unbind_x11(self):
        target = self.rootfs / "tmp/.X11-unix"
        if os.path.ismount(target):
            runner.run(["umount", "-l", target], quiet=True, check=False)

    # Running commands --------------------------------------------------
    def env(self, extra=None, interactive=False):
        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/root",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TERM": os.environ.get("TERM", "xterm-256color"),
            "USER": "root",
            "LOGNAME": "root",
            "SHELL": "/bin/bash",
        }
        if not interactive:
            env.update({"DEBIAN_FRONTEND": "noninteractive",
                        "DEBCONF_NONINTERACTIVE_SEEN": "true",
                        "APT_LISTCHANGES_FRONTEND": "none"})
        if extra:
            env.update(extra)
        return env

    def command(self, cmd, env=None, interactive=False):
        chroot = runner.which("chroot") or "/usr/sbin/chroot"
        envargs = ["{}={}".format(k, v) for k, v in self.env(env, interactive).items()]
        return [chroot, str(self.rootfs), "/usr/bin/env", "-i"] + envargs + [str(c) for c in cmd]

    def run(self, cmd, env=None, **kw):
        with self:
            return runner.run(self.command(cmd, env), **kw)

    def output(self, cmd, env=None, **kw):
        with self:
            return runner.output(self.command(cmd, env), **kw)

    def shell(self, script, **kw):
        return self.run(["/bin/sh", "-ec", script], **kw)

    def interactive(self, cmd=None):
        """Attach an interactive shell to the current terminal."""
        import subprocess
        cmd = cmd or ["/bin/bash", "--login"]
        env = {"PS1": r"(eduka-chroot) \u@\h:\w\$ ", "HISTFILE": "/root/.eduka_history"}
        with self:
            return subprocess.call(self.command(cmd, env, interactive=True))

    def copy_in(self, src, rel_dest):
        dest = self.rootfs / str(rel_dest).lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest


def rootfs_path(rootfs, rel):
    return Path(rootfs) / str(rel).lstrip("/")
