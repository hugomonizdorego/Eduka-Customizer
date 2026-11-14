"""Default settings of the web browsers, as enterprise policies (Browser page).

Firefox ESR (Debian's firefox-esr) reads policies.json from
  /etc/firefox-esr/policies/policies.json      (Debian's own place)
  /etc/firefox/policies/policies.json          (every Firefox on Linux)
  /usr/lib/firefox-esr/distribution/policies.json
D!sco writes the same file to all three. Chromium reads every JSON file in
/etc/chromium/policies/managed/.

What can be set here: the home page (locked or not), bookmarks in the toolbar,
no telemetry, no "first run" pages, and the search engine of Firefox.
"""

import json
import re
from pathlib import Path

from disco.core.log import log

FIREFOX_PATHS = ["etc/firefox-esr/policies/policies.json", "etc/firefox/policies/policies.json",
                 "usr/lib/firefox-esr/distribution/policies.json"]
CHROMIUM_PATH = "etc/chromium/policies/managed/disco.json"
SEARCH = ["", "DuckDuckGo", "Google", "Bing", "Wikipedia (en)", "Qwant", "Startpage"]
URL = re.compile(r"^(https?|file)://\S+$")


def parse_bookmarks(text):
    """'Title | URL' lines (or just URLs) -> [(title, url)]."""
    out = []
    for n, line in enumerate((text or "").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        title, _, url = line.rpartition("|") if "|" in line else ("", "", line)
        title, url = title.strip() or url.strip(), url.strip()
        if not URL.match(url):
            raise ValueError("Bookmark line {}: '{}' is not a web address (https://...)".format(n, url))
        out.append((title, url))
    return out


def firefox_policies(homepage="", locked=False, bookmarks=(), telemetry=False, search=""):
    p = {}
    if homepage:
        if not URL.match(homepage):
            raise ValueError("The home page must be a web address (https://...)")
        p["Homepage"] = {"URL": homepage, "Locked": bool(locked), "StartPage": "homepage"}
    if bookmarks:
        p["DisplayBookmarksToolbar"] = "always"
        p["Bookmarks"] = [{"Title": t, "URL": u, "Placement": "toolbar"} for t, u in bookmarks]
    if not telemetry:
        p["DisableTelemetry"] = True
        p["DisableFirefoxStudies"] = True
    p["OverrideFirstRunPage"] = ""
    p["OverridePostUpdatePage"] = ""
    p["DontCheckDefaultBrowser"] = True
    if search:
        if search not in SEARCH:
            raise ValueError("Unknown search engine: {}".format(search))
        p["SearchEngines"] = {"Default": search}
    return {"policies": p}


def chromium_policies(homepage="", locked=False, bookmarks=(), telemetry=False):
    p = {}
    if homepage:
        p.update({"HomepageLocation": homepage, "HomepageIsNewTabPage": False, "ShowHomeButton": True,
                  "RestoreOnStartup": 4, "RestoreOnStartupURLs": [homepage]})
    if bookmarks:
        p["BookmarkBarEnabled"] = True
        p["ManagedBookmarks"] = [{"toplevel_name": "Bookmarks"}] + [{"name": t, "url": u} for t, u in bookmarks]
    if not telemetry:
        p["MetricsReportingEnabled"] = False
    p["PromotionalTabsEnabled"] = False
    return p


def apply(project, homepage="", locked=False, bookmarks_text="", telemetry=False, search="",
          firefox=True, chromium=True):
    """Write the policies into the image. Returns the files written."""
    bookmarks = parse_bookmarks(bookmarks_text)
    r = Path(project.rootfs)
    written = []
    if firefox:
        data = json.dumps(firefox_policies(homepage, locked, bookmarks, telemetry, search), indent=2) + "\n"
        for rel in FIREFOX_PATHS:
            p = r / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(data)
            p.chmod(0o644)
            written.append("/" + rel)
    if chromium:
        p = r / CHROMIUM_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(chromium_policies(homepage, locked, bookmarks, telemetry), indent=2) + "\n")
        p.chmod(0o644)
        written.append("/" + CHROMIUM_PATH)
    project.state["browser"] = {"homepage": homepage, "locked": bool(locked), "bookmarks": bookmarks_text,
                                "telemetry": bool(telemetry), "search": search, "firefox": firefox,
                                "chromium": chromium}
    project.save()
    project.record("browser-policies", homepage or "defaults")
    log.info("Browser policies written: %s", ", ".join(written))
    return written


def remove(project):
    r = Path(project.rootfs)
    for rel in FIREFOX_PATHS + [CHROMIUM_PATH]:
        if (r / rel).exists():
            (r / rel).unlink()
    project.state.pop("browser", None)
    project.save()
