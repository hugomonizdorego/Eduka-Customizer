"""Design the GRUB menu of the ISO: rename, reorder, remove and add entries,
choose the default entry, the timeout and the colors.

grub.cfg is read into its top-level parts (menu entries, submenus and the text
around them). The result is saved like a manual edit (bootedit), so it is
kept for every build.
"""

import re
from pathlib import Path

from eduka_customizer.core import bootedit

KEY = "boot/grub/grub.cfg"
ENTRY = re.compile(r"^\s*(menuentry|submenu)\s+(['\"])(.*?)(?<!\\)\2(.*)$")
COLORS = ["black", "blue", "green", "cyan", "red", "magenta", "brown", "light-gray", "dark-gray", "light-blue",
          "light-green", "light-cyan", "light-red", "light-magenta", "yellow", "white"]
PRESETS = [
    ("live", "Live system", ""),
    ("safe", "Live system (safe graphics)", "nomodeset"),
    ("toram", "Live system (copy to RAM)", "toram"),
    ("verbose", "Live system (show boot messages)", "-quiet -splash"),
    ("failsafe", "Live system (fail-safe)", "memtest noapic noapm nodma nomce nosmp nosplash"),
    ("firmware", "UEFI firmware settings", None),
    ("reboot", "Restart", None),
    ("poweroff", "Power off", None),
]


def parse(text):
    """[('text', str) | ('entry', {'kind', 'title', 'head', 'body'})] of the top level."""
    parts, buf = [], []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        m = ENTRY.match(lines[i])
        if not m:
            buf.append(lines[i])
            i += 1
            continue
        if buf:
            parts.append(("text", "".join(buf)))
            buf = []
        block, depth, started = [], 0, False
        while i < len(lines):
            line = lines[i]
            block.append(line)
            code = re.sub(r"(['\"]).*?(?<!\\)\1", "", line)
            code = code.split("#")[0]
            depth += code.count("{") - code.count("}")
            started = started or "{" in code
            i += 1
            if started and depth <= 0:
                break
        head = block[0]
        parts.append(("entry", {"kind": m.group(1), "title": m.group(3).replace('\\"', '"'), "head": head,
                                "body": "".join(block[1:])}))
    if buf:
        parts.append(("text", "".join(buf)))
    return parts


def entries(text):
    return [p[1] for p in parse(text) if p[0] == "entry"]


def _retitle(entry):
    m = ENTRY.match(entry["head"])
    title = entry["title"].replace("\\", "").replace('"', "'")
    return '{} "{}"{}\n'.format(m.group(1), title, m.group(4).rstrip("\n")) if m else entry["head"]


def build(text, new_entries):
    """grub.cfg with the entries of *new_entries* (in that order) where the old ones were."""
    parts = parse(text)
    out, placed = [], False
    for kind, value in parts:
        if kind == "text":
            out.append(value)
        elif not placed:
            for e in new_entries:
                out.append(_retitle(e) + e["body"])
            placed = True
    if not placed:
        out.append("\n" + "".join(_retitle(e) + e["body"] for e in new_entries))
    return "".join(out)


def set_setting(text, name, value):
    """Set (or add near the top) 'set name=value'."""
    line = "set {}={}".format(name, value)
    if re.search(r"(?m)^\s*set {}=".format(re.escape(name)), text):
        return re.sub(r"(?m)^(\s*)set {}=.*$".format(re.escape(name)), lambda m: m.group(1) + line, text, count=1)
    # Before the first entry: after 'source' lines that may set it too.
    lines = text.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if ENTRY.match(l):
            return "".join(lines[:i]) + line + "\n" + "".join(lines[i:])
    return text.rstrip("\n") + "\n" + line + "\n"


def setting(text, name):
    m = re.search(r"(?m)^\s*set {}=(.*)$".format(re.escape(name)), text)
    return m.group(1).strip().strip('"') if m else ""


def preset_entry(text, preset):
    """A new entry from a preset, built from the first live entry of the menu."""
    key, title, extra = next(p for p in PRESETS if p[0] == preset)
    if extra is None:
        body = {"firmware": "    fwsetup\n", "reboot": "    reboot\n", "poweroff": "    halt\n"}[key]
        return {"kind": "menuentry", "title": title, "head": 'menuentry "{}" {{\n'.format(title),
                "body": body + "}\n"}
    live = next((e for e in entries(text) if "boot=live" in e["body"]), None)
    if not live:
        raise ValueError("No live entry in the menu to copy from")
    body = live["body"]
    m = re.search(r"(?m)^(\s*linux\S*\s+\S+)(.*)$", body)
    if not m:
        raise ValueError("The live entry has no 'linux' line")
    opts = m.group(2).split()
    for x in extra.split():
        if x.startswith("-"):
            opts = [o for o in opts if o != x[1:]]
        elif x not in opts:
            opts.append(x)
    body = body[:m.start()] + m.group(1) + " " + " ".join(opts) + body[m.end():]
    name = live["title"].split("(")[0].strip()
    if key != "live":
        title = "{} ({})".format(name, title.split("(", 1)[1].rstrip(")")) if "(" in title else title
    else:
        title = name
    return {"kind": "menuentry", "title": title, "head": 'menuentry "{}" {{\n'.format(title), "body": body}


class GrubMenu:
    def __init__(self, project):
        self.project = project
        self.path = Path(project.isodir) / KEY

    def read(self):
        return self.path.read_text(errors="replace") if self.path.exists() else ""

    def design(self):
        text = self.read()
        return {"entries": entries(text), "default": setting(text, "default"), "timeout": setting(text, "timeout"),
                "normal": setting(text, "menu_color_normal"), "highlight": setting(text, "menu_color_highlight")}

    def save(self, new_entries, default=None, timeout=None, normal=None, highlight=None):
        """Write the designed menu (kept for every build) and return the new grub.cfg."""
        if not new_entries:
            raise ValueError("The menu needs at least one entry")
        text = build(self.read(), new_entries)
        if default is not None:
            titles = [e["title"] for e in new_entries]
            if default not in titles:
                raise ValueError("The default entry is not in the menu")
            text = set_setting(text, "default", '"{}"'.format(default.replace('"', "'")))
        if timeout not in (None, ""):
            text = set_setting(text, "timeout", str(int(timeout)))
        for name, value in (("menu_color_normal", normal), ("menu_color_highlight", highlight)):
            if value:
                fg, _, bg = value.partition("/")
                if fg not in COLORS or bg not in COLORS:
                    raise ValueError("Colors must be GRUB color names, e.g. white/black")
                text = set_setting(text, name, value)
        problems = [p for p in bootedit.validate(self.project, KEY, text) if "copied there by the build" not in p]
        if problems:
            raise ValueError("The menu would not work:\n" + "\n".join(problems))
        bootedit.save(self.project, KEY, text, keep=True)
        self.project.record("grub-menu", "{} entries".format(len(new_entries)))
        return text
