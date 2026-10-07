"""Plymouth boot splash: install themes from any format, preview, apply, remove."""

import re
import shutil
import subprocess
import time
from pathlib import Path

from eduka_customizer.core.apt import Packages
from eduka_customizer.core.branding import PLYMOUTH_THEMES, SAFE, Branding
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

ARCHIVES = (".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tar.zst", ".zip")
FORMATS = "Plymouth themes (*.plymouth *.deb *.zip *.tar *.tar.gz *.tgz *.tar.xz *.txz *.tar.bz2 *.tbz2)"
CONF = "etc/plymouth/plymouthd.conf"


def _ini_get(text, key):
    m = re.search(r"(?m)^\s*{}\s*=\s*(.*?)\s*$".format(re.escape(key)), text)
    return m.group(1) if m else ""


class Plymouth:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.branding = Branding(project)
        self.chroot = Chroot(project.rootfs)

    @property
    def base(self):
        return self.rootfs / PLYMOUTH_THEMES

    def installed(self):
        return (self.rootfs / "usr/sbin/plymouthd").exists() or (self.rootfs / "sbin/plymouthd").exists()

    def current(self):
        return self.branding.plymouth_current()

    def _owners(self):
        """Map theme name -> package that ships it (from the dpkg file lists)."""
        owners = {}
        info = self.rootfs / "var/lib/dpkg/info"
        if not info.is_dir():
            return owners
        pat = re.compile(r"^/usr/share/plymouth/themes/([^/]+)/[^/]+\.plymouth$", re.M)
        for lst in info.glob("*.list"):
            try:
                text = lst.read_text(errors="replace")
            except OSError:
                continue
            if "/plymouth/themes/" not in text:
                continue
            for name in pat.findall(text):
                owners.setdefault(name, lst.stem.split(":")[0])
        return owners

    def themes(self):
        owners = self._owners()
        cur = self.current()
        result = []
        for name in self.branding.plymouth_themes():
            d = self.base / name
            pf = d / (name + ".plymouth")
            if not pf.exists():
                found = sorted(d.glob("*.plymouth"))
                pf = found[0] if found else pf
            text = pf.read_text(errors="replace") if pf.exists() else ""
            result.append({"name": name, "title": _ini_get(text, "Name") or name,
                           "description": _ini_get(text, "Description"),
                           "module": _ini_get(text, "ModuleName"), "owner": owners.get(name, ""),
                           "current": name == cur, "path": str(d), "preview": self.preview_image(name)})
        return result

    def preview_image(self, name):
        d = self.base / name
        if not d.is_dir():
            return ""
        pngs = [p for p in d.rglob("*.png") if p.is_file()]
        for wanted in ("preview", "screenshot", "background", "watermark", "logo", "header-image", "bgrt-fallback"):
            for p in pngs:
                if p.stem.lower().startswith(wanted):
                    return str(p)
        if pngs:
            return str(max(pngs, key=lambda p: p.stat().st_size))
        return ""

    # Install -----------------------------------------------------------------
    def install(self, source):
        """Install a theme from a folder, a .plymouth file, an archive or a .deb."""
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(source)
        before = set(self.branding.plymouth_themes())
        if source.suffix == ".deb":
            Packages(self.project).install_debs([source])
            new = sorted(set(self.branding.plymouth_themes()) - before)
            name = new[0] if new else self._theme_in_deb(source)
        elif source.suffix == ".plymouth":
            name = self.branding.import_plymouth(source.parent)
        elif source.is_dir() or source.name.lower().endswith(ARCHIVES):
            name = self.branding.import_plymouth(source)
        else:
            raise ValueError("Unsupported theme format: {} (use a folder, .plymouth, .deb, .zip or "
                             ".tar.*)".format(source.name))
        if not name:
            raise RuntimeError("No Plymouth theme found in {}".format(source.name))
        self.project.record("plymouth-install", name)
        return name

    def _theme_in_deb(self, deb):
        out = subprocess.run(["dpkg-deb", "-c", str(deb)], capture_output=True, text=True).stdout
        m = re.search(r"/usr/share/plymouth/themes/([^/\s]+)/[^/\s]+\.plymouth", out)
        return m.group(1) if m else ""

    def packages(self):
        """Theme packages APT offers for the image: (name, description, installed)."""
        pkgs = Packages(self.project)
        installed = {p[0] for p in pkgs.installed()}
        found = [(n, d) for n, d in pkgs.search("plymouth-theme")
                 if n.startswith("plymouth-theme") or n == "plymouth-themes"]
        return [(n, d, n in installed) for n, d in sorted(found)]

    def install_packages(self, names):
        with self.chroot:
            self.branding.ensure_plymouth()
            Packages(self.project).install(names)

    # Apply / remove ------------------------------------------------------------
    def apply(self, name):
        self.branding.set_plymouth(name)

    def remove(self, name):
        if not SAFE.match(name):
            raise ValueError("Invalid theme name")
        if name == self.current():
            raise ValueError("{} is the current theme: choose another theme first".format(name))
        owner = self._owners().get(name)
        if owner:
            if owner in ("plymouth", "plymouth-themes"):
                raise ValueError("{} is part of the package {}, which also holds other themes and "
                                 "cannot be removed alone".format(name, owner))
            Packages(self.project).remove([owner])
        else:
            target = self.base / name
            if not target.is_dir():
                raise FileNotFoundError("Theme {} is not installed".format(name))
            shutil.rmtree(target)
        self.project.record("plymouth-remove", name)
        log.info("Removed Plymouth theme %s", name)

    # Settings ---------------------------------------------------------------------
    def settings(self):
        p = self.rootfs / CONF
        text = p.read_text(errors="replace") if p.exists() else ""
        return {"show_delay": _ini_get(text, "ShowDelay") or "0",
                "device_scale": _ini_get(text, "DeviceScale") or "auto"}

    def set_settings(self, show_delay=0, device_scale="auto"):
        from eduka_customizer.core.branding import _ini_set
        values = {"ShowDelay": str(max(0, int(show_delay)))}
        if device_scale in ("1", "2"):
            values["DeviceScale"] = device_scale
        p = self.rootfs / CONF
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text("[Daemon]\n")
        _ini_set(p, "Daemon", values)
        if device_scale not in ("1", "2"):
            p.write_text(re.sub(r"(?m)^\s*DeviceScale\s*=.*\n?", "", p.read_text()))
        self.project.mark_initramfs_dirty()

    # Preview ------------------------------------------------------------------------
    def x11_renderer(self):
        return any(self.rootfs.glob("usr/lib/*/plymouth/renderers/x11.so")) or \
            any(self.rootfs.glob("usr/lib/plymouth/renderers/x11.so"))

    def preview(self, name, seconds=10, resolution="1024x768"):
        """Show the theme in a window (plymouthd with the X11 renderer inside Xephyr)."""
        from eduka_customizer.core.livesession import LiveSession
        if name not in self.branding.plymouth_themes():
            raise ValueError("Theme {} is not installed".format(name))
        if not self.x11_renderer():
            log.info("Installing plymouth-x11 (needed to show themes in a window)")
            Packages(self.project).install(["plymouth-x11"])
        old = self.current()
        seconds = max(3, min(60, int(seconds)))
        with self.chroot:
            self.branding.write_plymouth_default(name)
        script = PREVIEW.format(n=seconds,
                                title=self.project.state.get("identity", {}).get("name", "Edukasaun OS"))
        live = LiveSession(self.project)
        live.start(resolution=resolution, mode="root", command="/bin/sh -c '{}'".format(script.replace("'", "")))
        try:
            deadline = time.time() + seconds + 60
            while live.running and live.session and live.session.poll() is None and time.time() < deadline:
                time.sleep(0.5)
        finally:
            live.stop()
            if old and self.current() != old:
                with self.chroot:
                    self.branding.write_plymouth_default(old)


PREVIEW = (
    # The kernel command line is the host's: give plymouthd one that asks for the splash and
    # makes it skip serial consoles and udev, so the X11 renderer (plymouth-x11) is used.
    "plymouthd --no-daemon --debug --debug-file=/tmp/plymouth-preview.log "
    "--kernel-command-line=\"quiet splash plymouth.ignore-serial-consoles plymouth.ignore-udev\" & P=$!; "
    "w=0; until plymouth --ping || [ $w -gt 60 ]; do sleep 0.5; w=$((w+1)); done; "
    "plymouth show-splash; "
    "i=0; while [ $i -lt {n} ]; do i=$((i+1)); "
    "plymouth system-update --progress=$((i*100/{n})) 2>/dev/null; "
    "plymouth display-message --text=\"{title}: preview $i/{n}\"; sleep 1; done; "
    "plymouth ask-for-password --prompt=Password --dont-pause-progress >/dev/null 2>&1 & A=$!; sleep 3; kill $A 2>/dev/null; "
    "plymouth quit; sleep 1; kill $P 2>/dev/null")
