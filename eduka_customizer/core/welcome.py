"""Welcome screen: four pages you design (title, text, logo, picture, colors and
buttons) shown when a user logs in, until they untick 'Show this at startup'.

The screen is a small GTK 3 program (/usr/bin/eduka-welcome, needs python3-gi)
that reads /usr/share/eduka-welcome/welcome.json, so it works on every desktop.
Text may use **bold**, *italic* and [links](https://example.org).
"""

import copy
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from eduka_customizer.core import imaging
from eduka_customizer.core.config import data_file
from eduka_customizer.core.log import log

PAGES = 4
DATA = "usr/share/eduka-welcome"
APP = "usr/bin/eduka-welcome"
DESKTOP = "usr/share/applications/eduka-welcome.desktop"
AUTOSTART = "etc/xdg/autostart/eduka-welcome.desktop"
PACKAGES = ["python3-gi", "gir1.2-gtk-3.0", "xdg-utils"]
ACTIONS = [("url", "Open a website"), ("command", "Start a program"), ("installer", "Start the installer"),
           ("close", "Close the welcome screen")]
SHOW = [("startup", "At every login, until the user unticks it"), ("live", "Only in the live session"),
        ("installed", "Only on the installed system"), ("menu", "Only from the menu")]
POSITIONS = [("right", "Right of the text"), ("left", "Left of the text"), ("top", "Above the text"),
             ("bottom", "Below the text")]
COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def default_design(project):
    name = project.display_name()
    home = project.state.get("identity", {}).get("home_url", "")
    pages = [
        {"title": "Welcome to {}".format(name),
         "text": "Thank you for choosing **{}**.\n\nThis short tour shows you around. Press *Next* to "
                 "continue.".format(name),
         "buttons": [{"label": "Website", "action": "url", "target": home}] if home else []},
        {"title": "Install {}".format(name),
         "text": "You are trying {} without changing your computer. When you like it, install it with "
                 "the installer.".format(name),
         "buttons": [{"label": "Install now", "action": "installer", "target": ""}]},
        {"title": "Applications",
         "text": "Find more applications in the software center or install them with the package manager.",
         "buttons": []},
        {"title": "Get help",
         "text": "Questions? Visit the website or ask the community.",
         "buttons": [{"label": "Help", "action": "url", "target": home}] if home else []},
    ]
    for p in pages:
        p.update({"enabled": True, "image": "", "image_position": "right", "show_logo": True,
                  "align": "center", "background": ""})
    return {"enabled": True, "title": "Welcome to {}".format(name), "width": 860, "height": 560,
            "show": "startup", "logo": "", "startup_label": "Show this at startup",
            "back_label": "Back", "next_label": "Next", "close_label": "Close",
            "colors": {"background": "#ffffff", "text": "#1d2b28", "title": "#00a879", "accent": "#00a879",
                       "button_text": "#ffffff"},
            "pages": pages}


def design(project):
    """The project's design (complete, with four pages)."""
    d = default_design(project)
    saved = project.state.get("welcome")
    if saved:
        pages = saved.get("pages", [])
        d.update({k: v for k, v in saved.items() if k != "pages"})
        d["colors"] = dict(default_design(project)["colors"], **(saved.get("colors") or {}))
        for i in range(PAGES):
            if i < len(pages):
                d["pages"][i].update(pages[i])
    return d


def to_markup(text):
    """**bold**, *italic*, [text](url) -> Pango/Qt markup; everything else escaped."""
    out = html.escape(text or "", quote=True)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|mailto:[^)\s]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", out)
    return out


def validate(d):
    problems = []
    for key, value in (d.get("colors") or {}).items():
        if value and not COLOR.match(value):
            problems.append("Color {} must look like #00a879".format(key))
    pages = d.get("pages", [])
    if len(pages) != PAGES:
        problems.append("A welcome screen has {} pages".format(PAGES))
    if not any(p.get("enabled", True) for p in pages):
        problems.append("Turn on at least one page")
    for n, p in enumerate(pages, 1):
        if p.get("enabled", True) and not (p.get("title") or p.get("text")):
            problems.append("Page {} has no title and no text".format(n))
        if p.get("background") and not COLOR.match(p["background"]):
            problems.append("Page {}: background must look like #ffffff".format(n))
        for b in p.get("buttons", []):
            if not b.get("label"):
                continue
            if b.get("action") not in dict(ACTIONS):
                problems.append("Page {}: unknown button action {}".format(n, b.get("action")))
            elif b["action"] == "url" and not re.match(r"^(https?://|mailto:|file:/)", b.get("target", "")):
                problems.append("Page {}: the button '{}' needs a web address (https://...)".format(n, b["label"]))
            elif b["action"] == "command" and not b.get("target", "").strip():
                problems.append("Page {}: the button '{}' needs a program to start".format(n, b["label"]))
    for key in ("width", "height"):
        if not 300 <= int(d.get(key, 600)) <= 3000:
            problems.append("The window {} must be between 300 and 3000 pixels".format(key))
    if d.get("show") not in dict(SHOW):
        problems.append("Unknown 'show' setting")
    return problems


def render(d, folder):
    """Write welcome.json and the pictures for design *d* into *folder*. Returns the JSON written."""
    folder = Path(folder)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    out = copy.deepcopy(d)
    if d.get("logo") and Path(d["logo"]).is_file():
        imaging.write_png(d["logo"], folder / "logo.png", (256, 256), fit="contain")
        out["logo"] = "logo.png"
    else:
        out["logo"] = ""
    for n, p in enumerate(out["pages"], 1):
        src = d["pages"][n - 1].get("image")
        if src and Path(src).is_file():
            name = "page{}.png".format(n)
            imaging.write_png(src, folder / name, (900, 700), fit="contain")
            p["image"] = name
        else:
            p["image"] = ""
        p["title_markup"] = to_markup(p.get("title", ""))
        p["text_markup"] = to_markup(p.get("text", ""))
    (folder / "welcome.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return out


def app_source():
    return data_file("welcome", "eduka-welcome")


class Welcome:
    def __init__(self, project):
        self.project = project
        self.rootfs = Path(project.rootfs)

    def save(self, d):
        problems = validate(d)
        if problems:
            raise ValueError("\n".join(problems))
        self.project.state["welcome"] = d
        self.project.save()

    def installed(self):
        return (self.rootfs / APP).exists() and (self.rootfs / DATA / "welcome.json").exists()

    def apply(self, d=None, install_packages=True):
        d = d or design(self.project)
        self.save(d)
        r = self.rootfs
        if install_packages:
            from eduka_customizer.core.apt import Packages
            pk = Packages(self.project)
            missing = [p for p in PACKAGES if not pk.is_installed(p)]
            if missing:
                with pk.chroot:
                    ok = pk.available(missing)
                    if "python3-gi" in missing and "python3-gi" not in ok:
                        raise RuntimeError("python3-gi is not available in the image's APT sources")
                    pk.install([p for p in missing if p in ok])
        render(d, r / DATA)
        (r / APP).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app_source(), r / APP)
        (r / APP).chmod(0o755)
        icon = "/" + DATA + "/logo.png" if (r / DATA / "logo.png").exists() else "system-help"
        entry = ("[Desktop Entry]\nType=Application\nName={}\nComment=Welcome screen\nExec=eduka-welcome\n"
                 "Icon={}\nCategories=System;Utility;\nTerminal=false\n").format(d.get("title", "Welcome"), icon)
        (r / DESKTOP).parent.mkdir(parents=True, exist_ok=True)
        (r / DESKTOP).write_text(entry)
        auto = r / AUTOSTART
        if d.get("enabled", True) and d.get("show") != "menu":
            auto.parent.mkdir(parents=True, exist_ok=True)
            auto.write_text(entry.replace("Exec=eduka-welcome", "Exec=eduka-welcome --autostart") +
                            "NoDisplay=true\nX-GNOME-Autostart-Delay=3\n")
        elif auto.exists():
            auto.unlink()
        self.project.record("welcome", "{} page(s)".format(sum(1 for p in d["pages"] if p.get("enabled", True))))
        log.info("Welcome screen installed: %s", d.get("title"))

    def remove(self):
        r = self.rootfs
        for rel in (APP, DESKTOP, AUTOSTART):
            if (r / rel).exists():
                (r / rel).unlink()
        if (r / DATA).exists():
            shutil.rmtree(r / DATA)
        self.project.record("welcome", "removed")

    def preview(self, d, folder, screenshot=None):
        """Show the design on this computer (needs python3-gi here). Returns the process."""
        problems = validate(d)
        if problems:
            raise ValueError("\n".join(problems))
        render(d, folder)
        cmd = [sys.executable if Path(sys.executable).name.startswith("python3") else "python3",
               str(app_source()), "--data", str(folder)]
        if screenshot:
            cmd += ["--screenshot", str(screenshot)]
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
