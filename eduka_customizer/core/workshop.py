"""Package Workshop: open an installed Debian package, edit it, rebuild it.

This is the direct way to change Debian packages such as base-files,
lsb-release, distro-info-data, desktop-base or plymouth-themes. The files
of the installed package are copied (dpkg-repack style) into
PROJECT/workshop/<package>/ together with its control data. Edit anything,
then build: the version gets a "+<id>N" suffix, the package is installed
into the image and can be put on hold so Debian updates do not replace it.
"""

import os
import re
import shutil

from eduka_customizer.core import debpkg, runner
from eduka_customizer.core.apt import APT, Packages, parse_deb822
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

BRANDING_PACKAGES = [
    ("base-files", "/etc/issue, /etc/os-release, /etc/debian_version, motd"),
    ("lsb-release", "lsb_release -a output (or lsb-release-minimal)"),
    ("lsb-release-minimal", "lsb_release from os-release"),
    ("distro-info-data", "release metadata (/usr/share/distro-info)"),
    ("desktop-base", "wallpapers, GRUB and login artwork, Debian logos"),
    ("plymouth-themes", "boot splash themes"),
    ("grub-common", "GRUB scripts (/etc/grub.d)"),
    ("calamares-settings-debian", "graphical installer settings and branding"),
    ("debian-archive-keyring", "APT keys of the Debian archive"),
]
SCRIPT_NAMES = ["preinst", "postinst", "prerm", "postrm", "config", "templates", "triggers",
                "shlibs", "symbols"]
DROP_FIELDS = {"Status", "Conffiles", "Config-Version", "Installed-Size"}


class Workshop:
    def __init__(self, project):
        self.project = project
        self.base = project.path / "workshop"

    def path(self, package):
        return self.base / package

    def opened(self):
        if not self.base.is_dir():
            return []
        return sorted(p.name for p in self.base.iterdir() if (p / "DEBIAN/control").exists())

    def _stanza(self, package):
        status = self.project.rootfs / "var/lib/dpkg/status"
        for st in parse_deb822(status.read_text(errors="replace")):
            if st.get("Package") == package and "install ok installed" in st.get("Status", ""):
                return st
        raise ValueError("{} is not installed in the image".format(package))

    def _info(self, package, st, suffix):
        info = self.project.rootfs / "var/lib/dpkg/info"
        arch = st.get("Architecture", "")
        for name in ("{}:{}.{}".format(package, arch, suffix), "{}.{}".format(package, suffix)):
            if (info / name).exists():
                return info / name
        return None

    def _diversions(self, package):
        """Map original path -> diverted path for files that *another* package
        (or the admin) diverted away. A package's own diversions do not apply
        to its own files (e.g. base-files diverts /bin for usrmerge)."""
        result = {}
        f = self.project.rootfs / "var/lib/dpkg/diversions"
        if not f.exists():
            return result
        lines = f.read_text(errors="replace").splitlines()
        for i in range(0, len(lines) - 2, 3):
            if lines[i + 2] != package:
                result[lines[i]] = lines[i + 1]
        return result

    def _listed(self, package):
        st = self._stanza(package)
        listing = self._info(package, st, "list")
        return [l for l in listing.read_text(errors="replace").splitlines() if l and l != "/."]

    def verify(self, package):
        """Refuse to build a package that lost files of the original: dpkg would
        delete them from the image on upgrade (this can break the system)."""
        root = self.path(package)
        missing = [p for p in self._listed(package) if not os.path.lexists(str(root) + p)]
        return missing

    def open(self, package):
        """Copy an installed package into an editable dpkg-deb tree."""
        runner.require("rsync")
        st = self._stanza(package)
        listing = self._info(package, st, "list")
        if not listing:
            raise RuntimeError("File list of {} not found".format(package))
        target = self.path(package)
        if target.exists():
            shutil.rmtree(target)
        (target / "DEBIAN").mkdir(parents=True)
        paths = [l for l in listing.read_text(errors="replace").splitlines() if l and l != "/."]
        diversions = self._diversions(package)
        plain = [p.lstrip("/") for p in paths if p not in diversions]
        files_from = self.base / (package + ".files")
        files_from.write_text("\n".join(plain) + "\n")
        log.info("Copying %d files of %s", len(paths), package)
        runner.run(["rsync", "-a", "--no-recursive", "--files-from", files_from,
                    str(self.project.rootfs) + "/", str(target) + "/"], ok_codes=(0, 23), quiet=True)
        files_from.unlink()
        for original, moved in diversions.items():
            if original in paths:
                src = self.project.rootfs / moved.lstrip("/")
                if src.exists() or src.is_symlink():
                    dest = target / original.lstrip("/")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest, follow_symlinks=False)
        lines = []
        for key, value in st.items():
            if key in DROP_FIELDS:
                continue
            first, *rest = value.split("\n")
            lines.append("{}: {}".format(key, first))
            lines += [" " + r for r in rest]
        (target / "DEBIAN/control").write_text("\n".join(lines) + "\n")
        conffiles = [l.split()[0] for l in st.get("Conffiles", "").split("\n") if l.strip()]
        if conffiles:
            (target / "DEBIAN/conffiles").write_text("\n".join(conffiles) + "\n")
        for script in SCRIPT_NAMES:
            src = self._info(package, st, script)
            if src:
                shutil.copy2(src, target / "DEBIAN" / script)
        (target / "DEBIAN").chmod(0o755)
        info = self.project.state.setdefault("workshop", {}).setdefault(package, {})
        info.setdefault("original", st.get("Version", ""))
        self.project.record("workshop-open", package)
        return target

    def control(self, package):
        return parse_deb822((self.path(package) / "DEBIAN/control").read_text())[0]

    def files(self, package):
        root = self.path(package)
        return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                      if (p.is_file() or p.is_symlink()) and "DEBIAN" not in p.relative_to(root).parts[:1])

    def build(self, package, tag=None, hold=True, install=True, allow_missing=False):
        root = self.path(package)
        missing = self.verify(package)
        if missing and not allow_missing:
            raise RuntimeError("These files of the original {} are missing in the workshop copy; "
                               "installing it would delete them from the image:\n{}".format(
                                   package, "\n".join(missing[:30])))
        ctrl_file = root / "DEBIAN/control"
        st = parse_deb822(ctrl_file.read_text())[0]
        tag = tag or (self.project.state.get("identity", {}).get("id") or "custom")
        version = debpkg.bump_version(st["Version"], tag)
        text = ctrl_file.read_text()
        text = re.sub(r"(?m)^Version:.*$", "Version: " + version, text)
        size = sum(p.stat().st_size for p in root.rglob("*")
                   if p.is_file() and not p.is_symlink() and "DEBIAN" not in p.parts) // 1024 + 1
        if re.search(r"(?m)^Installed-Size:", text):
            text = re.sub(r"(?m)^Installed-Size:.*$", "Installed-Size: {}".format(size), text)
        else:
            text = text.rstrip("\n") + "\nInstalled-Size: {}\n".format(size)
        ctrl_file.write_text(text)
        out_dir = self.project.path / "workshop-debs"
        out_dir.mkdir(exist_ok=True)
        arch = st.get("Architecture", "all")
        deb = out_dir / "{}_{}_{}.deb".format(package, version.split(":")[-1], arch)
        runner.require("dpkg-deb")
        log.info("Building %s", deb.name)
        runner.run(["dpkg-deb", "-Zxz", "--build", root, deb], quiet=True)
        if install:
            Packages(self.project).install_debs([deb], reinstall=True)
            chroot = Chroot(self.project.rootfs)
            chroot.run(["apt-mark", "hold" if hold else "unhold", package], quiet=True)
        self.project.mark_initramfs_dirty()
        self.project.state.setdefault("workshop", {}).setdefault(package, {}).update(
            {"version": version, "hold": hold})
        self.project.record("workshop-build", "{} {}".format(package, version))
        return deb

    def restore(self, package):
        """Unhold and reinstall Debian's version of the package."""
        original = self.project.state.get("workshop", {}).get(package, {}).get("original")
        chroot = Chroot(self.project.rootfs)
        with chroot:
            chroot.run(["apt-mark", "unhold", package], quiet=True)
            Packages(self.project).update()
            target = "{}={}".format(package, original) if original else package
            chroot.run(APT + ["install", "--reinstall", "--allow-downgrades", target])
        self.project.state.get("workshop", {}).pop(package, None)
        self.project.record("workshop-restore", package)

    def close(self, package):
        shutil.rmtree(self.path(package), ignore_errors=True)
