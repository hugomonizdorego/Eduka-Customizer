"""Package lists: the programs of the distribution, in files you tick and edit.

Every list is a plain text file in <project>/lists, named NN-name.list (01 is
installed before 02). One Debian package per line; '#' starts a comment and
'-name' removes a package. The files can also be changed with any text editor.
A list that is switched off stays in the folder but is not installed.

The lists come on top of the base system (made by "Build base"); a package that
is already there is simply kept. Packages that the release or the processor of
the image does not have are skipped with a note instead of stopping the build.
"""

import json
import re
from pathlib import Path

from disco.core.apt import read_package_list
from disco.core.config import data_file
from disco.core.log import log

LIST_DIR = "lists"
FILE = re.compile(r"^(\d{2})-([a-z0-9][a-z0-9.+-]*)\.list$")
PACKAGE = re.compile(r"^-?[a-z0-9][a-z0-9+.\-]*(:[a-z0-9]+)?$")


def slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s[:40] or "list"


def catalog():
    """The tick-box catalog: [{id, name, icon, apps: [(package, name, description)]}]."""
    with open(data_file("catalog.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    return [dict(c, apps=[tuple(a) for a in c["apps"]]) for c in data["categories"]]


def section_groups():
    """{Debian section: (group id, group name)} for friendly categories in the package browser."""
    with open(data_file("catalog.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    names = data.get("section_names", {})
    out = {}
    for group, sections in data.get("debian_sections", {}).items():
        for s in sections:
            out.setdefault(s, (group, names.get(group, group.title())))
    return out


def friendly_section(section):
    """'net' or 'contrib/net' -> 'Internet'."""
    s = (section or "").split("/")[-1]
    return section_groups().get(s, ("other", "Other"))[1]


class PackageList:
    def __init__(self, path):
        self.path = Path(path)
        m = FILE.match(self.path.name)
        self.number = int(m.group(1)) if m else 99
        self.slug = m.group(2) if m else self.path.stem

    @property
    def name(self):
        return self.path.name

    @property
    def title(self):
        """The title in the first comment line ('# Title: ...'), else from the file name."""
        try:
            for line in self.path.read_text(errors="replace").splitlines()[:3]:
                if line.lower().startswith("# title:"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return self.slug.replace("-", " ").capitalize()

    def read(self):
        """(install, remove) package names."""
        if not self.path.exists():
            return [], []
        return read_package_list(self.path)

    def packages(self):
        inst, rem = self.read()
        return inst + ["-" + r for r in rem]

    def comment(self):
        lines = []
        for line in self.path.read_text(errors="replace").splitlines() if self.path.exists() else []:
            if line.startswith("#") and not line.lower().startswith("# title:"):
                lines.append(line[1:].strip())
            elif line.strip():
                break
        return "\n".join(lines)

    def write(self, packages, title=None, comment=None):
        names = []
        for p in packages:
            p = p.strip()
            if not p or p in names:
                continue
            if not PACKAGE.match(p):
                raise ValueError("Not a Debian package name: {}".format(p))
            names.append(p)
        title = title if title is not None else self.title
        comment = comment if comment is not None else (self.comment() if self.path.exists() else "")
        head = ["# Title: " + title] + ["# " + c for c in comment.splitlines() if c.strip()]
        self.path.write_text("\n".join(head + names) + "\n")


class Lists:
    def __init__(self, project):
        self.project = project
        self.dir = Path(project.path) / LIST_DIR

    # Reading --------------------------------------------------------------------------------
    def all(self):
        if not self.dir.is_dir():
            return []
        return sorted((PackageList(p) for p in self.dir.glob("*.list")), key=lambda l: (l.number, l.name))

    def get(self, name):
        for l in self.all():
            if l.name == name or l.slug == name:
                return l
        raise KeyError("No package list called {}".format(name))

    def _off(self):
        return set(self.project.state.setdefault("lists", {}).setdefault("off", []))

    def is_on(self, pl):
        return pl.name not in self._off()

    def set_on(self, pl, on=True):
        off = self._off()
        (off.discard if on else off.add)(pl.name)
        self.project.state["lists"]["off"] = sorted(off)
        self.project.save()

    def plan(self):
        """(install, remove) of all lists that are on, in their order; a later list wins."""
        install, remove = [], []
        for pl in self.all():
            if not self.is_on(pl):
                continue
            inst, rem = pl.read()
            for p in inst:
                if p in remove:
                    remove.remove(p)
                if p not in install:
                    install.append(p)
            for p in rem:
                if p in install:
                    install.remove(p)
                if p not in remove:
                    remove.append(p)
        return install, remove

    # Changing ------------------------------------------------------------------------------------
    def create(self, title, packages=(), comment="", number=None):
        self.dir.mkdir(parents=True, exist_ok=True)
        used = {l.number for l in self.all()}
        if number is None:
            number = max(used | {0}) + 1
            number = (number + 9) // 10 * 10 if number > 1 else 10
            while number in used:
                number += 1
        if number > 99:
            raise ValueError("There are too many package lists (99 at most)")
        pl = PackageList(self.dir / "{:02d}-{}.list".format(number, slug(title)))
        if pl.path.exists():
            raise FileExistsError("{} exists already".format(pl.name))
        pl.write(packages, title=title, comment=comment)
        self.project.record("list-new", pl.name)
        return pl

    def delete(self, pl):
        off = self._off()
        off.discard(pl.name)
        self.project.state["lists"]["off"] = sorted(off)
        pl.path.unlink()
        self.project.save()
        self.project.record("list-delete", pl.name)

    def rename(self, pl, title):
        packages = pl.packages()
        new = PackageList(pl.path.with_name("{:02d}-{}.list".format(pl.number, slug(title))))
        if new.path != pl.path and new.path.exists():
            raise FileExistsError("{} exists already".format(new.name))
        on = self.is_on(pl)
        pl.write(packages, title=title)
        if new.path != pl.path:
            pl.path.rename(new.path)
            self._rename_state(pl.name, new.name, on)
        return new

    def _rename_state(self, old, new, on):
        off = self._off()
        off.discard(old)
        if not on:
            off.add(new)
        self.project.state["lists"]["off"] = sorted(off)
        self.project.save()

    def move(self, pl, delta):
        """Move a list up (-1) or down (+1): the lists are numbered 10, 20, 30... again."""
        lists = self.all()
        i = [l.path for l in lists].index(pl.path)
        j = max(0, min(len(lists) - 1, i + delta))
        if i == j:
            return pl
        lists.insert(j, lists.pop(i))
        return self.renumber(lists, follow=pl)

    def renumber(self, lists=None, follow=None):
        lists = lists if lists is not None else self.all()
        states = {l.name: self.is_on(l) for l in lists}
        temp = []
        for i, l in enumerate(lists):
            t = l.path.with_name(".renumber-{}-{}".format(i, l.path.name))
            l.path.rename(t)
            temp.append((t, l))
        result = None
        off = set()
        for i, (t, l) in enumerate(temp):
            target = self.dir / "{:02d}-{}.list".format((i + 1) * 10 if len(lists) < 10 else i + 1, l.slug)
            t.rename(target)
            if not states[l.name]:
                off.add(target.name)
            if follow is not None and l.path == follow.path:
                result = PackageList(target)
        self.project.state.setdefault("lists", {})["off"] = sorted(off)
        self.project.save()
        return result

    def add(self, pl, names):
        cur = pl.packages()
        for n in names:
            if n not in cur:
                cur.append(n)
        pl.write(cur)

    def remove(self, pl, names):
        pl.write([p for p in pl.packages() if p not in set(names)])

    # Defaults -------------------------------------------------------------------------------------
    @staticmethod
    def defaults(plat, profile=None, installer="calamares"):
        """{file name: {title, on, packages, comment}}: the first lists of a project for platform *plat*."""
        kernel = [plat.kernel] + list(plat.packages)
        if plat.arch in ("amd64", "i386"):
            from disco.core.bootstrap import PC_FIRMWARE
            kernel += PC_FIRMWARE
        apps = []
        if profile:
            try:
                from disco.core import profiles
                apps = list(profiles.get(profile).get("packages", []))
            except KeyError:
                apps = []
        data = {
            "10-kernel-and-firmware.list": {
                "title": "Kernel and firmware", "packages": kernel,
                "comment": "The kernel and the firmware of {}.\nAlso installed with the base system; add more "
                           "firmware here.".format(plat.name)},
            "20-system-tools.list": {
                "title": "System tools", "comment": "Small programs every system needs.",
                "packages": ["sudo", "network-manager", "bash-completion", "nano", "less", "htop", "curl", "wget",
                             "unzip", "zstd", "rsync"]},
            "30-applications.list": {
                "title": "Applications", "packages": apps,
                "comment": "Programs for the menu: tick them in the catalog or type their names."},
            "50-my-packages.list": {
                "title": "My packages", "packages": [],
                "comment": "Your own additions. '-name' removes a package."},
        }
        if plat.output == "iso" and installer == "calamares":
            data["40-installer.list"] = {
                "title": "Installer", "packages": ["calamares", "calamares-settings-debian"],
                "comment": "Calamares installs the live system on a disk. Switch this list off for a live-only "
                           "system."}
        return data

    def ensure_defaults(self, plat=None, profile=None, installer="calamares"):
        """Write the first lists of a project (only when it has none)."""
        if self.all():
            return False
        from disco.core import platforms
        self.load(self.defaults(plat or platforms.of_project(self.project), profile, installer), replace=False)
        log.info("Package lists written to %s", self.dir)
        return True

    # Installing ---------------------------------------------------------------------------------------
    def install(self, stage=None):
        """Install the lists that are on (and remove what they remove).
        Returns (installed, skipped): skipped packages are not in the image's repositories."""
        from disco.core.apt import Packages
        install, remove = self.plan()
        pk = Packages(self.project)
        have = {p[0] for p in pk.installed()}
        skipped = []
        with pk.chroot:
            pk.recover()
            pk.update()
            todo = [p for p in install if p.split(":")[0] not in have]
            if todo:
                known = pk.available(todo)
                skipped = [p for p in todo if p not in known]
                todo = [p for p in todo if p in known]
            if skipped:
                log.warning("Not in the repositories of this release and processor, skipped: %s",
                            " ".join(skipped))
            if todo:
                if stage:
                    stage("Installing {} package(s) from the lists".format(len(todo)))
                pk.install(todo, update=False)
            gone = [p for p in remove if p in have]
            if gone:
                if stage:
                    stage("Removing {} package(s)".format(len(gone)))
                pk.remove(gone)
        self.project.state.setdefault("lists", {})["skipped"] = skipped
        self.project.save()
        return todo, skipped

    def export(self, path):
        """All lists in one JSON file (for presets)."""
        data = {l.name: {"title": l.title, "on": self.is_on(l), "packages": l.packages(), "comment": l.comment()}
                for l in self.all()}
        Path(path).write_text(json.dumps(data, indent=1) + "\n")

    def load(self, data, replace=True):
        """Lists from a preset: {file name: {title, on, packages, comment}}."""
        self.dir.mkdir(parents=True, exist_ok=True)
        if replace:
            for l in self.all():
                l.path.unlink()
            self.project.state.setdefault("lists", {})["off"] = []
        off = set(self.project.state.setdefault("lists", {}).get("off", []))
        for name, entry in sorted(data.items()):
            if not FILE.match(name):
                raise ValueError("Not a package list name: {} (use NN-name.list)".format(name))
            pl = PackageList(self.dir / name)
            pl.write(entry.get("packages", []), title=entry.get("title") or pl.title,
                     comment=entry.get("comment", ""))
            if not entry.get("on", True):
                off.add(name)
        self.project.state["lists"]["off"] = sorted(off)
        self.project.save()
