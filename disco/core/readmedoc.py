"""A PDF about your distribution, on the desktop of every user (Desktop document page).

You give it any title and text (a first text is written from the project: name,
base, desktop, programs, how to install it). D!sco makes the PDF and puts it into
the system:

  /usr/share/doc/<id>-guide/<Title>.pdf             the document
  /etc/xdg/autostart/<id>-guide-desktop.desktop     copies it to the desktop once, at the first login
                                                    (the live user too), into the desktop folder of
                                                    the user's language (xdg-user-dir DESKTOP)
  /usr/share/applications/<id>-guide.desktop        "<Title>" in the menu
"""

import html
import re
import shutil
from pathlib import Path

from disco.core.log import log

SCRIPT = """#!/bin/sh
# Puts "{title}" on the desktop once, at the first login (written by D!sco).
marker="${{XDG_CONFIG_HOME:-$HOME/.config}}/{id}-guide-on-desktop"
[ -e "$marker" ] && exit 0
desk=$(xdg-user-dir DESKTOP 2>/dev/null)
if [ -z "$desk" ] || [ "$desk" = "$HOME" ]; then desk="$HOME/Desktop"; fi
mkdir -p "$desk"
cp -n '/usr/share/doc/{id}-guide/{file}' "$desk/" 2>/dev/null
chmod 644 "$desk/{file}" 2>/dev/null
mkdir -p "$(dirname "$marker")" && touch "$marker"
exit 0
"""
AUTOSTART = """[Desktop Entry]
Type=Application
Name={title} on the desktop
Exec=/usr/share/{id}-guide/put-on-desktop
NoDisplay=true
X-GNOME-Autostart-Phase=Applications
"""
MENU = """[Desktop Entry]
Type=Application
Name={title}
Comment=About {name}
Exec=xdg-open '/usr/share/doc/{id}-guide/{file}'
Icon=x-office-document
Categories=Documentation;
"""


def file_name(title):
    """A file name from a free title (letters of any language, digits, spaces, - _ .)."""
    name = re.sub(r"[^\w .-]", "", title, flags=re.UNICODE).strip(" .")
    return (name or "README")[:80] + ".pdf"


def default_html(project):
    """A first text that describes the system, made from the project."""
    from disco.core import platforms
    ident = project.state.get("identity") or {}
    b = project.state.get("builder") or {}
    name = ident.get("name") or b.get("distro_name") or project.display_name()
    version = ident.get("version") or ""
    d = project.distro
    family = "Devuan" if (b.get("family") == "devuan" or getattr(d, "is_devuan", False)) else "Debian"
    base = "{} {}".format(family, d.debian_codename or b.get("suite") or "").strip()
    plat = platforms.of_project(project)
    desk = ""
    de_id = (project.state.get("desktop") or {}).get("id") or b.get("desktop")
    if de_id:
        try:
            from disco.core import desktop as dsk
            desk = dsk.desktop(de_id)["name"]
        except KeyError:
            desk = de_id
    apps = []
    try:
        from disco.core.pkglists import Lists, catalog
        names = {pkg: title for cat in catalog() for pkg, title, _d in cat["apps"]}
        inst, _rem = Lists(project).plan()
        apps = [names[p] for p in inst if p in names]
    except (OSError, ValueError, KeyError):
        pass
    esc = html.escape
    parts = ["<h1>{} {}</h1>".format(esc(name), esc(version)),
             "<p><b>{}</b> is a free operating system built on <b>{}</b> for <b>{}</b>.</p>".format(
                 esc(name), esc(base), esc(plat.name))]
    if desk:
        parts.append("<p>The desktop is <b>{}</b>.</p>".format(esc(desk)))
    if apps:
        parts.append("<h2>Programs</h2><p>{}</p>".format(esc(", ".join(apps[:40]))))
    parts.append("<h2>Getting started</h2><ul>"
                 "<li>Programs are in the menu of the desktop.</li>"
                 "<li>Install more programs with the software center or, in a terminal, with "
                 "<code>sudo apt install name</code>.</li>"
                 "<li>Keep the system up to date: <code>sudo apt update &amp;&amp; sudo apt full-upgrade</code>.</li>"
                 "</ul>")
    if plat.output == "iso":
        parts.append("<h2>Installing</h2><p>Start the computer from the USB stick, try the live system, then "
                     "start the installer from the desktop or the menu to put {} on the disk.</p>".format(esc(name)))
    else:
        parts.append("<h2>The SD card</h2><p>At the first start the system grows to the whole card and makes new "
                     "SSH keys. The file sysconf.txt on the boot partition sets the computer name and an SSH key "
                     "before the first start.</p>")
    links = [(t, ident.get(k)) for t, k in (("Website", "home_url"), ("Help", "support_url"),
                                            ("Report a problem", "bug_url")) if ident.get(k)]
    if links:
        parts.append("<h2>Links</h2><ul>{}</ul>".format("".join(
            "<li>{}: <a href=\"{}\">{}</a></li>".format(esc(t), esc(u), esc(u)) for t, u in links)))
    parts.append("<p><small>The programs of this system are free software; their licenses are in "
                 "/usr/share/doc/*/copyright.</small></p>")
    return "\n".join(parts)


def make_pdf(title, body_html, out):
    """Write the PDF (A4) with Qt. Returns the file."""
    from disco.core import imaging
    gui = imaging._qt()
    if gui is None:
        raise RuntimeError("Qt is needed to make PDF files")
    from disco.qt import core
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    writer = gui.QPdfWriter(str(out))
    writer.setTitle(title)
    writer.setCreator("D!sco")
    page = gui.QPageLayout(gui.QPageSize(gui.QPageSize.PageSizeId.A4), gui.QPageLayout.Orientation.Portrait,
                           core.QMarginsF(18, 18, 18, 18), gui.QPageLayout.Unit.Millimeter)
    writer.setPageLayout(page)
    writer.setResolution(300)
    doc = gui.QTextDocument()
    doc.documentLayout().setPaintDevice(writer)     # measure the text for the PDF (300 dpi), not the screen
    font = doc.defaultFont()
    font.setPointSizeF(11)
    doc.setDefaultFont(font)
    doc.setDefaultStyleSheet("h1 { color: #1d3557; } h2 { color: #264653; } code { background: #eeeeee; }")
    doc.setHtml(body_html)
    rect = writer.pageLayout().paintRectPixels(writer.resolution())
    doc.setPageSize(core.QSizeF(rect.width(), rect.height()))
    if hasattr(doc, "print_"):      # PyQt5
        doc.print_(writer)
    else:                           # PyQt6
        doc.print(writer)
    return out


def install(project, pdf, title):
    """Put the PDF into the system: documentation folder, desktop at the first login, menu."""
    r = Path(project.rootfs)
    os_id = project.os_id()
    fname = file_name(title)
    safe_title = re.sub(r"['\"\\\\$`\n]", "", title).strip() or "README"
    doc_dir = r / "usr/share/doc/{}-guide".format(os_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    for old in doc_dir.glob("*.pdf"):
        old.unlink()
    shutil.copy2(pdf, doc_dir / fname)
    (doc_dir / fname).chmod(0o644)
    script = r / "usr/share/{}-guide/put-on-desktop".format(os_id)
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(SCRIPT.format(title=safe_title, id=os_id, file=fname.replace("'", "")))
    script.chmod(0o755)
    auto = r / "etc/xdg/autostart/{}-guide-desktop.desktop".format(os_id)
    auto.parent.mkdir(parents=True, exist_ok=True)
    auto.write_text(AUTOSTART.format(title=safe_title, id=os_id))
    menu = r / "usr/share/applications/{}-guide.desktop".format(os_id)
    menu.parent.mkdir(parents=True, exist_ok=True)
    menu.write_text(MENU.format(title=safe_title, name=project.display_name(), id=os_id, file=fname))
    project.state["readme"] = {"title": title, "file": fname}
    project.save()
    project.record("desktop-document", fname)
    log.info("Desktop document %s added", fname)
    return doc_dir / fname


def remove(project):
    r = Path(project.rootfs)
    os_id = project.os_id()
    for p in (r / "usr/share/doc/{}-guide".format(os_id), r / "usr/share/{}-guide".format(os_id)):
        if p.is_dir():
            shutil.rmtree(p)
    for p in (r / "etc/xdg/autostart/{}-guide-desktop.desktop".format(os_id),
              r / "usr/share/applications/{}-guide.desktop".format(os_id)):
        if p.exists():
            p.unlink()
    project.state.pop("readme", None)
    project.save()
