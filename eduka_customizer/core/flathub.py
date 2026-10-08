"""The Flathub catalog, by category (Office, Audio & Video, Games, ...).

The catalog comes straight from Flathub: first its public API (flathub.org),
otherwise Flathub's own AppStream metadata downloaded by flatpak inside the
image. It is kept in the project cache so browsing works offline, and
'Update' fetches it again.
"""

import gzip
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from eduka_customizer.core.config import settings
from eduka_customizer.core.log import log

# Flathub's main categories (freedesktop.org main categories) and their names on flathub.org.
CATEGORIES = [
    ("Office", "Productivity & Office"),
    ("AudioVideo", "Audio & Video"),
    ("Graphics", "Graphics & Photography"),
    ("Network", "Networking & Internet"),
    ("Education", "Education"),
    ("Science", "Science"),
    ("Game", "Games"),
    ("Development", "Developer Tools"),
    ("System", "System"),
    ("Utility", "Utilities"),
]
CATEGORY_IDS = [c for c, _n in CATEGORIES]
# Older category names that Flathub still uses for some applications.
ALIASES = {"Audio": "AudioVideo", "Video": "AudioVideo", "Utilities": "Utility", "Games": "Game",
           "Productivity": "Office", "Networking": "Network", "Internet": "Network"}
# A few well-known applications, one or two per category, used by the Quick Wizard.
FEATURED = [
    ("org.mozilla.firefox", "Firefox", "Web browser", "Network"),
    ("org.mozilla.Thunderbird", "Thunderbird", "E-mail, calendar and chat", "Network"),
    ("org.libreoffice.LibreOffice", "LibreOffice", "Office suite", "Office"),
    ("org.onlyoffice.desktopeditors", "ONLYOFFICE", "Office suite compatible with Microsoft Office", "Office"),
    ("org.videolan.VLC", "VLC", "Media player", "AudioVideo"),
    ("org.audacityteam.Audacity", "Audacity", "Audio editor", "AudioVideo"),
    ("com.obsproject.Studio", "OBS Studio", "Screen recording and streaming", "AudioVideo"),
    ("org.kde.kdenlive", "Kdenlive", "Video editor", "AudioVideo"),
    ("org.gimp.GIMP", "GIMP", "Image editor", "Graphics"),
    ("org.inkscape.Inkscape", "Inkscape", "Vector graphics", "Graphics"),
    ("org.kde.krita", "Krita", "Digital painting", "Graphics"),
    ("org.blender.Blender", "Blender", "3D creation", "Graphics"),
    ("org.kde.gcompris", "GCompris", "Educational activities for children", "Education"),
    ("org.geogebra.GeoGebra", "GeoGebra", "Dynamic mathematics", "Education"),
    ("org.stellarium.Stellarium", "Stellarium", "Planetarium", "Science"),
    ("org.zotero.Zotero", "Zotero", "Research assistant", "Science"),
    ("com.valvesoftware.Steam", "Steam", "Games store", "Game"),
    ("org.supertuxproject.SuperTux", "SuperTux", "Platform game", "Game"),
    ("com.visualstudio.code", "Visual Studio Code", "Code editor", "Development"),
    ("org.gnome.Builder", "Builder", "IDE for GNOME", "Development"),
    ("io.github.flattool.Warehouse", "Warehouse", "Manage Flatpak applications", "System"),
    ("com.github.tchx84.Flatseal", "Flatseal", "Flatpak permissions", "System"),
    ("org.keepassxc.KeePassXC", "KeePassXC", "Password manager", "Utility"),
    ("org.gnome.Calculator", "Calculator", "Calculator", "Utility"),
]
CACHE = "flathub-catalog.json"


def category_of(categories):
    """The main category of an app (the first of Flathub's list it belongs to)."""
    cats = [ALIASES.get(c, c) for c in categories or []]
    for c in CATEGORY_IDS:
        if c in cats:
            return c
    return "Utility"


def _norm_id(hit):
    app_id = hit.get("app_id") or hit.get("flatpakAppId") or hit.get("id") or ""
    return app_id.replace("_", ".") if "." not in app_id else app_id


def from_api(timeout=30, per_page=250, progress=None):
    """{app_id: {name, summary, category}} from the Flathub API, category by category."""
    api = settings().get("flatpak", "api_url").rstrip("/")
    out = {}
    for cat, title in CATEGORIES:
        page, pages = 1, 1
        while page <= pages and page <= 40:
            if progress:
                progress("Flathub: {} (page {})".format(title, page))
            url = "{}/collection/category/{}?page={}&per_page={}".format(api, cat, page, per_page)
            req = urllib.request.Request(url, headers={"User-Agent": "Eduka-Customizer",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            hits = data.get("hits", data if isinstance(data, list) else [])
            pages = int(data.get("totalPages") or data.get("total_pages") or 1) if isinstance(data, dict) else 1
            for hit in hits:
                app_id = _norm_id(hit)
                if not app_id or app_id in out:
                    continue
                cats = hit.get("main_categories") or hit.get("categories") or [cat]
                if isinstance(cats, str):
                    cats = [cats]
                out[app_id] = {"name": hit.get("name") or app_id, "summary": hit.get("summary") or "",
                               "category": category_of(list(cats) + [cat])}
            page += 1
    return out


def from_appstream(path):
    """{app_id: {...}} from Flathub's AppStream XML (appstream.xml or .xml.gz)."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    out = {}
    with opener(path, "rb") as fh:
        for _ev, el in ET.iterparse(fh, events=("end",)):
            if el.tag != "component":
                continue
            if el.get("type", "desktop") in ("desktop", "desktop-application", "console-application"):
                app_id = (el.findtext("id") or "").strip()
                if app_id.endswith(".desktop"):
                    app_id = app_id[:-len(".desktop")]
                lang = "{http://www.w3.org/XML/1998/namespace}lang"
                name = next((n.text for n in el.findall("name") if n.get(lang) is None and n.text), app_id)
                summary = next((n.text for n in el.findall("summary") if n.get(lang) is None and n.text), "")
                cats = [c.text for c in el.findall("categories/category") if c.text]
                if app_id and app_id not in out:
                    out[app_id] = {"name": name.strip(), "summary": summary.strip(), "category": category_of(cats)}
            el.clear()
    return out


def appstream_file(rootfs, remote="flathub"):
    base = Path(rootfs, "var/lib/flatpak/appstream", remote)
    for f in sorted(base.glob("*/active/appstream.xml.gz")) + sorted(base.glob("*/active/appstream.xml")):
        return f
    return None


class Catalog:
    def __init__(self, project):
        self.project = project
        self.path = Path(project.cache) / CACHE

    def load(self):
        """(apps, info) from the cache; apps is empty when nothing was fetched yet."""
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text())
                return data.get("apps", {}), {"source": data.get("source", ""), "time": data.get("time", 0)}
            except (OSError, ValueError):
                pass
        return {}, {"source": "", "time": 0}

    def update(self, progress=None):
        """Fetch the catalog from Flathub (API, otherwise AppStream via flatpak in the image)."""
        source, apps = "", {}
        try:
            apps = from_api(progress=progress)
            source = "flathub.org API"
        except (OSError, ValueError) as e:
            log.warning("Flathub API unreachable (%s): using Flathub's AppStream data through flatpak", e)
        if not apps:
            from eduka_customizer.core.chroot import Chroot
            from eduka_customizer.core.flatpak import Flatpak
            fp = Flatpak(self.project)
            if not fp.available():
                fp.setup()
            if progress:
                progress("Downloading Flathub's AppStream data")
            with Chroot(self.project.rootfs) as ch:
                ch.run(["flatpak", "remote-add", "--system", "--if-not-exists", fp.remote, fp.remote_url],
                       check=False)
                ch.run(["flatpak", "update", "--system", "--appstream", "-y", fp.remote], check=False)
            f = appstream_file(self.project.rootfs, fp.remote)
            if not f:
                raise RuntimeError("Could not get the Flathub catalog: no internet connection?")
            apps = from_appstream(f)
            source = "Flathub AppStream ({})".format(f.name)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"source": source, "time": int(time.time()), "apps": apps}))
        log.info("Flathub catalog: %d applications (%s)", len(apps), source)
        return apps

    @staticmethod
    def by_category(apps, category=None, text=""):
        """Sorted [(app_id, name, summary, category)] filtered by category and search text."""
        text = text.lower().strip()
        rows = []
        for app_id, a in apps.items():
            if category and a.get("category") != category:
                continue
            if text and text not in app_id.lower() and text not in a.get("name", "").lower() \
                    and text not in a.get("summary", "").lower():
                continue
            rows.append((app_id, a.get("name", app_id), a.get("summary", ""), a.get("category", "")))
        return sorted(rows, key=lambda r: r[1].lower())

    @staticmethod
    def counts(apps):
        out = {c: 0 for c in CATEGORY_IDS}
        for a in apps.values():
            out[a.get("category", "Utility")] = out.get(a.get("category", "Utility"), 0) + 1
        return out
