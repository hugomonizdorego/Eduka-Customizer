"""User accounts of the image.

Two kinds of accounts:

* The **live user** is created by live-config every time the ISO boots
  (Debian's default is "user" with the password "live"). Its name, full
  name, password (or no password at all), autologin and groups are set in
  /etc/live/config.conf.d and a small live-config script.
* **Image accounts** are real accounts inside the root filesystem
  (/etc/passwd). They exist in the live session *and* are copied to every
  computer installed from the ISO with Calamares.
"""

import re
import shutil
import subprocess

from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

USERNAME = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOSTNAME = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
RESERVED = {"root", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp",
            "proxy", "www-data", "backup", "list", "irc", "nobody", "systemd-network", "messagebus",
            "sshd", "polkitd", "lightdm", "sddm", "gdm", "avahi", "colord", "pulse", "rtkit"}
LIVE_CONF = "etc/live/config.conf.d/50-edukasaun.conf"
LIVE_SCRIPT = "live/config/1999-eduka-password"
DEFAULT_GROUPS = ["audio", "cdrom", "dip", "floppy", "video", "plugdev", "netdev", "powerdev", "scanner",
                  "bluetooth", "lpadmin"]
PASSWORD_MODES = {"default": "Debian default password ('live')",
                  "custom": "This password",
                  "none": "No password (log in without a password)"}


def check_username(name):
    if not USERNAME.match(name or ""):
        raise ValueError("Invalid user name '{}': use lower-case letters, digits, '-' and '_', "
                         "starting with a letter (at most 32 characters)".format(name))
    if name in RESERVED:
        raise ValueError("'{}' is a system account name".format(name))


def _clean_text(text):
    """Full names end up in shell and passwd files: keep them simple."""
    return re.sub(r'[":\\$`\n]', "", text or "").strip()


def sha512_crypt(password):
    """$6$ hash for /etc/shadow, made with openssl (crypt left Python in 3.13)."""
    exe = shutil.which("openssl")
    if not exe:
        raise RuntimeError("openssl is needed to hash the password")
    out = subprocess.run([exe, "passwd", "-6", "-stdin"], input=password + "\n", text=True,
                         capture_output=True, check=True).stdout.strip()
    if not out.startswith("$6$"):
        raise RuntimeError("openssl did not return a SHA-512 hash")
    return out


def _read_conf(path):
    values = {}
    if path.exists():
        for m in re.finditer(r'(?m)^\s*([A-Z_]+)="?([^"\n]*)"?\s*$', path.read_text(errors="replace")):
            values[m.group(1)] = m.group(2)
    return values


class Users:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.chroot = Chroot(project.rootfs)

    # Live user -------------------------------------------------------------
    def _script(self):
        lib = self.rootfs / "lib"
        base = "lib" if lib.is_dir() and not lib.is_symlink() else "usr/lib"
        return self.rootfs / base / LIVE_SCRIPT

    def live(self):
        conf = _read_conf(self.rootfs / LIVE_CONF)
        script = self._script()
        mode = "default"
        if script.exists():
            mode = "none" if "passwd -d" in script.read_text(errors="replace") else "custom"
        ident = self.project.state.get("identity", {})
        return {"username": conf.get("LIVE_USERNAME") or ident.get("live_user") or "user",
                "fullname": conf.get("LIVE_USER_FULLNAME") or ident.get("live_fullname") or "Live user",
                "hostname": conf.get("LIVE_HOSTNAME") or ident.get("hostname") or "",
                "password": mode,
                "autologin": conf.get("LIVE_CONFIG_NOAUTOLOGIN", "false") != "true",
                "groups": [g for g in conf.get("LIVE_USER_DEFAULT_GROUPS", "").split() if g] or list(DEFAULT_GROUPS),
                "configured": (self.rootfs / LIVE_CONF).exists()}

    def set_live(self, username, fullname="", password_mode="default", password="", autologin=True,
                 groups=None, hostname=None, keep_password=False, password_hash=None):
        """Configure the live user created by live-config at every boot.

        keep_password leaves the password setting as it is (used by the Identity page).
        """
        check_username(username)
        if keep_password:
            password_mode = self.live()["password"]
        elif password_mode not in PASSWORD_MODES:
            raise ValueError("Unknown password mode: {}".format(password_mode))
        if password_hash and not password_hash.startswith(("$6$", "$y$", "$5$")):
            raise ValueError("password_hash must be a crypt(3) hash such as $6$...")
        if password_mode == "custom" and not (password or password_hash) and not keep_password:
            raise ValueError("Type a password, or choose 'No password'")
        hostname = hostname if hostname is not None else self.live()["hostname"]
        if hostname and not HOSTNAME.match(hostname):
            raise ValueError("Invalid host name: {}".format(hostname))
        groups = [g for g in (groups if groups is not None else DEFAULT_GROUPS) if g]
        bad = [g for g in groups if not USERNAME.match(g)]
        if bad:
            raise ValueError("Invalid group name(s): {}".format(", ".join(bad)))
        fullname = _clean_text(fullname) or username
        lines = ["# Live user, written by Eduka-Customizer (Users page)"]
        if hostname:
            lines.append('LIVE_HOSTNAME="{}"'.format(hostname))
        lines += ['LIVE_USERNAME="{}"'.format(username), 'LIVE_USER_FULLNAME="{}"'.format(fullname),
                  'LIVE_USER_DEFAULT_GROUPS="{}"'.format(" ".join(groups))]
        if not autologin:
            lines.append('LIVE_CONFIG_NOAUTOLOGIN="true"')
        conf = self.rootfs / LIVE_CONF
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text("\n".join(lines) + "\n")
        if not keep_password:
            self._write_password_script(password_mode, password, password_hash)
        ident = self.project.state.setdefault("identity", {})
        ident.update({"live_user": username, "live_fullname": fullname})
        if hostname:
            ident["hostname"] = hostname
        self.project.save()
        self.project.record("live-user", "{} ({})".format(username, password_mode))
        log.info("Live user: %s, password: %s", username, PASSWORD_MODES[password_mode])

    def _write_password_script(self, mode, password="", password_hash=None):
        script = self._script()
        if mode == "default":
            script.unlink(missing_ok=True)
            return
        if mode == "none":
            action = "passwd -d \"$LIVE_USERNAME\" >/dev/null"
        else:
            hashed = password_hash or sha512_crypt(password)
            if "'" in hashed or "\n" in hashed:
                raise ValueError("Invalid password hash")
            action = "usermod -p '{}' \"$LIVE_USERNAME\"".format(hashed)
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(LIVE_PASSWORD.format(action=action))
        script.chmod(0o755)

    def remove_live(self):
        """Forget the custom live user: Debian's defaults ("user" / "live") apply again."""
        (self.rootfs / LIVE_CONF).unlink(missing_ok=True)
        self._script().unlink(missing_ok=True)
        # live-config's own defaults
        self.project.state.setdefault("identity", {}).update({"live_user": "user", "live_fullname": "Debian Live user"})
        self.project.save()
        self.project.record("live-user", "removed (Debian default)")

    # Image accounts -----------------------------------------------------------
    def accounts(self):
        """Regular accounts in the image (UID 1000-59999)."""
        passwd = self.rootfs / "etc/passwd"
        shadow = self.rootfs / "etc/shadow"
        pw = {}
        if shadow.exists():
            for line in shadow.read_text(errors="replace").splitlines():
                parts = line.split(":")
                if len(parts) > 1:
                    pw[parts[0]] = parts[1]
        groups = self._groups()
        out = []
        if not passwd.exists():
            return out
        for line in passwd.read_text(errors="replace").splitlines():
            parts = line.split(":")
            if len(parts) < 7 or not parts[2].isdigit():
                continue
            uid = int(parts[2])
            if not 1000 <= uid < 60000:
                continue
            h = pw.get(parts[0], "")
            state = "no password" if h == "" else ("locked" if h.startswith(("!", "*")) else "password set")
            out.append({"username": parts[0], "uid": uid, "fullname": parts[4].split(",")[0],
                        "home": parts[5], "shell": parts[6], "password": state,
                        "groups": sorted(g for g, members in groups.items() if parts[0] in members)})
        return out

    def _groups(self):
        out = {}
        g = self.rootfs / "etc/group"
        if g.exists():
            for line in g.read_text(errors="replace").splitlines():
                parts = line.split(":")
                if len(parts) >= 4:
                    out[parts[0]] = [m for m in parts[3].split(",") if m]
        return out

    def _exists(self, username):
        return any(a["username"] == username for a in self.accounts())

    def add_account(self, username, fullname="", password=None, admin=False, groups=None, shell="/bin/bash",
                    password_hash=None):
        """Create an account in the image; password None (or empty) means no password."""
        check_username(username)
        if self._exists(username):
            raise ValueError("The account {} already exists".format(username))
        if shell not in ("/bin/bash", "/bin/sh", "/usr/bin/zsh", "/usr/bin/fish"):
            raise ValueError("Unsupported shell: {}".format(shell))
        known = self._groups()
        wanted = [g for g in (groups if groups is not None else DEFAULT_GROUPS) if g in known]
        if admin and "sudo" in known:
            wanted.append("sudo")
        cmd = ["useradd", "--create-home", "--shell", shell, "--comment", _clean_text(fullname) or username]
        if wanted:
            cmd += ["--groups", ",".join(sorted(set(wanted)))]
        with self.chroot:
            self.chroot.run(cmd + [username])
            if password_hash:
                self.chroot.run(["usermod", "-p", password_hash, username], quiet=True)
            else:
                self._set_password(username, password)
        self.project.record("user-add", "{}{}".format(username, " (admin)" if admin else ""))
        log.info("Account %s created in the image", username)

    def _set_password(self, username, password):
        if password:
            self.chroot.run(["usermod", "-p", sha512_crypt(password), username], quiet=True)
        else:
            self.chroot.run(["passwd", "-d", username], quiet=True)

    def set_password(self, username, password=None):
        """Change the password; None or "" removes it (login without password)."""
        check_username(username)
        if not self._exists(username):
            raise ValueError("No account called {}".format(username))
        with self.chroot:
            self._set_password(username, password)
        self.project.record("user-password", "{} ({})".format(username, "set" if password else "removed"))

    def delete_account(self, username, remove_home=True):
        check_username(username)
        if not self._exists(username):
            raise ValueError("No account called {}".format(username))
        with self.chroot:
            self.chroot.run(["userdel"] + (["--remove"] if remove_home else []) + [username], check=False)
        if self._exists(username):
            raise RuntimeError("Could not delete the account {}".format(username))
        self.project.record("user-delete", username)
        log.info("Account %s deleted from the image", username)


LIVE_PASSWORD = """#!/bin/sh
# Live user password, written by Eduka-Customizer (Users page).
# Runs after live-config created the live user.
[ -e /var/lib/live/config/eduka-password ] && exit 0
for f in /etc/live/config.conf /etc/live/config.conf.d/*.conf; do [ -r "$f" ] && . "$f"; done
for arg in $(cat /proc/cmdline 2>/dev/null); do
    case "$arg" in live-config.username=*|username=*) LIVE_USERNAME="${{arg#*=}}" ;; esac
done
LIVE_USERNAME="${{LIVE_USERNAME:-user}}"
if id "$LIVE_USERNAME" >/dev/null 2>&1; then
    {action}
fi
mkdir -p /var/lib/live/config && touch /var/lib/live/config/eduka-password
"""
