"""Flatpak / Flathub support for the image."""

import json
import re
import urllib.parse
import urllib.request

from eduka_customizer.core.apt import Packages
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.config import settings
from eduka_customizer.core.log import log

APP_ID = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$")
FIRSTBOOT_LIST = "etc/eduka-customizer/flatpak-firstboot.list"
FIRSTBOOT_SCRIPT = "usr/libexec/eduka-flatpak-firstboot"
FIRSTBOOT_UNIT = "etc/systemd/system/eduka-flatpak-firstboot.service"

# Curated educational picks for Edukasaun OS (Flathub application IDs).
EDUCATION_PICKS = [
    ("org.kde.gcompris", "GCompris", "Educational activities for children"),
    ("org.tuxpaint.Tuxpaint", "Tux Paint", "Drawing program for children"),
    ("org.geogebra.GeoGebra", "GeoGebra", "Dynamic mathematics"),
    ("org.stellarium.Stellarium", "Stellarium", "Planetarium"),
    ("org.kde.kalzium", "Kalzium", "Periodic table of elements"),
    ("org.kde.marble", "Marble", "Virtual globe and atlas"),
    ("org.kde.kturtle", "KTurtle", "Learn programming with Logo"),
    ("org.kde.ktouch", "KTouch", "Touch typing tutor"),
    ("org.kde.kgeography", "KGeography", "Geography learning tool"),
    ("org.kde.parley", "Parley", "Vocabulary trainer"),
    ("org.kde.kbruch", "KBruch", "Practice fractions"),
    ("org.kde.minuet", "Minuet", "Music education"),
    ("net.ankiweb.Anki", "Anki", "Flashcards"),
    ("org.libreoffice.LibreOffice", "LibreOffice", "Office suite"),
    ("org.inkscape.Inkscape", "Inkscape", "Vector graphics"),
    ("org.gimp.GIMP", "GIMP", "Image editor"),
    ("org.kde.krita", "Krita", "Digital painting"),
    ("org.audacityteam.Audacity", "Audacity", "Audio editor"),
    ("org.videolan.VLC", "VLC", "Media player"),
    ("org.mozilla.firefox", "Firefox", "Web browser"),
    ("org.zotero.Zotero", "Zotero", "Research assistant"),
]

FIRSTBOOT_SH = """#!/bin/sh
# Installs Flatpak applications chosen in Eduka-Customizer on first boot.
set -u
LIST=/{list}
[ -s "$LIST" ] || exit 0
for i in $(seq 1 30); do
    getent hosts dl.flathub.org >/dev/null 2>&1 && break
    sleep 10
done
flatpak remote-add --system --if-not-exists {remote} {url} || exit 1
failed=0
while read -r app; do
    case "$app" in ''|'#'*) continue ;; esac
    flatpak install --system --noninteractive -y {remote} "$app" || failed=1
done < "$LIST"
[ "$failed" = 0 ] && systemctl disable eduka-flatpak-firstboot.service
exit 0
"""

FIRSTBOOT_SERVICE = """[Unit]
Description=Install Flatpak applications selected for Edukasaun OS
Wants=network-online.target
After=network-online.target
ConditionPathExists=/{list}
# Do not run in the live session, only on installed systems.
ConditionKernelCommandLine=!boot=live

[Service]
Type=oneshot
ExecStart=/{script}
TimeoutStartSec=3h

[Install]
WantedBy=multi-user.target
"""


def check_ids(ids):
    bad = [i for i in ids if not APP_ID.match(i)]
    if bad:
        raise ValueError("Invalid Flatpak application ID(s): {}".format(", ".join(bad)))


class Flatpak:
    def __init__(self, project):
        self.project = project
        self.chroot = Chroot(project.rootfs)
        cfg = settings()
        self.remote = cfg.get("flatpak", "remote_name")
        self.remote_url = cfg.get("flatpak", "remote_url")

    def available(self):
        return (self.project.rootfs / "usr/bin/flatpak").exists()

    def setup(self, store_plugin=True):
        """Install flatpak and register Flathub system-wide."""
        pkgs = ["flatpak"]
        if store_plugin:
            rootfs = self.project.rootfs
            if (rootfs / "usr/bin/plasma-discover").exists():
                pkgs.append("plasma-discover-backend-flatpak")
            if (rootfs / "usr/bin/gnome-software").exists():
                pkgs.append("gnome-software-plugin-flatpak")
        Packages(self.project).install(pkgs)
        log.info("Adding the %s remote", self.remote)
        self.chroot.run(["flatpak", "remote-add", "--system", "--if-not-exists",
                         self.remote, self.remote_url])
        self.project.record("flatpak-setup", self.remote_url)

    def install(self, ids):
        check_ids(ids)
        if not ids:
            return
        if not self.available():
            self.setup()
        log.info("Installing Flatpak apps: %s", " ".join(ids))
        with self.chroot:
            self.chroot.run(["flatpak", "remote-add", "--system", "--if-not-exists",
                             self.remote, self.remote_url])
            self.chroot.run(["flatpak", "install", "--system", "--noninteractive", "-y",
                             self.remote] + list(ids))
        self.project.record("flatpak-install", " ".join(ids))

    def uninstall(self, ids):
        check_ids(ids)
        self.chroot.run(["flatpak", "uninstall", "--system", "--noninteractive", "-y"] + list(ids))
        self.chroot.run(["flatpak", "uninstall", "--system", "--noninteractive", "-y", "--unused"],
                        check=False)
        self.project.record("flatpak-uninstall", " ".join(ids))

    def installed(self):
        if not self.available():
            return []
        out = self.chroot.output(["flatpak", "list", "--system", "--app",
                                  "--columns=application,name,version,size"], check=False)
        rows = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and APP_ID.match(parts[0]):
                rows.append((parts + ["", "", ""])[:4])
        return rows

    def search(self, term):
        """Search with the flatpak CLI inside the image (API fallback)."""
        if not self.available():
            return []
        with self.chroot:
            self.chroot.run(["flatpak", "update", "--system", "--appstream", "-y"], check=False,
                            quiet=True)
            out = self.chroot.output(["flatpak", "search", "--columns=application,name,description",
                                      term], check=False)
        rows = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and APP_ID.match(parts[0]):
                rows.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
        return rows

    # First boot installation ----------------------------------------
    def firstboot_list(self):
        p = self.project.rootfs / FIRSTBOOT_LIST
        if not p.exists():
            return []
        return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")]

    def set_firstboot(self, ids):
        """Defer installation to the first boot of the installed system."""
        check_ids(ids)
        rootfs = self.project.rootfs
        lst = rootfs / FIRSTBOOT_LIST
        unit = rootfs / FIRSTBOOT_UNIT
        script = rootfs / FIRSTBOOT_SCRIPT
        wants = rootfs / "etc/systemd/system/multi-user.target.wants/eduka-flatpak-firstboot.service"
        if not ids:
            for p in (lst, unit, script, wants):
                if p.exists() or p.is_symlink():
                    p.unlink()
            log.info("First-boot Flatpak installation disabled")
            return
        if not self.available():
            Packages(self.project).install(["flatpak"])
        lst.parent.mkdir(parents=True, exist_ok=True)
        lst.write_text("# Flatpak apps installed on first boot\n" + "\n".join(ids) + "\n")
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(FIRSTBOOT_SH.format(list=FIRSTBOOT_LIST, remote=self.remote,
                                              url=self.remote_url))
        script.chmod(0o755)
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(FIRSTBOOT_SERVICE.format(list=FIRSTBOOT_LIST, script=FIRSTBOOT_SCRIPT))
        wants.parent.mkdir(parents=True, exist_ok=True)
        if not wants.is_symlink():
            wants.symlink_to("/" + FIRSTBOOT_UNIT)
        self.project.state["flatpak"]["firstboot"] = list(ids)
        self.project.record("flatpak-firstboot", " ".join(ids))


def search_flathub(term, timeout=20):
    """Search Flathub through its public API. Returns (id, name, summary)."""
    term = term.strip()
    if not term:
        return []
    api = settings().get("flatpak", "api_url").rstrip("/")
    body = json.dumps({"query": term, "filters": []}).encode()
    req = urllib.request.Request(api + "/search", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "Eduka-Customizer"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    hits = data.get("hits", data if isinstance(data, list) else [])
    results = []
    for hit in hits:
        app_id = hit.get("app_id") or hit.get("id") or ""
        app_id = app_id.replace("_", ".") if "." not in app_id else app_id
        if APP_ID.match(app_id):
            results.append((app_id, hit.get("name", app_id), hit.get("summary", "")))
    return results


def flathub_url(app_id):
    return "https://flathub.org/apps/" + urllib.parse.quote(app_id)
