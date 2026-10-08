"""Build binary .deb packages from a small Debian source tree.

The trees written by Eduka-Customizer are valid Debian source packages
(debian/control, changelog, copyright, rules, install, maintainer scripts),
so they can also be built with dpkg-buildpackage and published in a real
repository later. For speed and to avoid needing debhelper on the host,
build_tree() assembles the binary package with dpkg-deb directly.
"""

import datetime
import email.utils
import re
import shutil
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.apt import parse_deb822
from eduka_customizer.core.log import log

BINARY_FIELDS = ["Package", "Source", "Version", "Architecture", "Maintainer", "Section",
                 "Priority", "Pre-Depends", "Depends", "Recommends", "Suggests", "Conflicts",
                 "Breaks", "Replaces", "Provides", "Homepage", "Description"]
SCRIPTS = ["preinst", "postinst", "prerm", "postrm", "config", "templates", "triggers"]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]+$")


def changelog_entry(package, version, maintainer, lines, distribution="unstable"):
    date = email.utils.format_datetime(datetime.datetime.now().astimezone())
    body = "\n".join("  * " + l for l in lines)
    return "{} ({}) {}; urgency=medium\n\n{}\n\n -- {}  {}\n".format(
        package, version, distribution, body, maintainer, date)


def changelog_version(path):
    m = re.match(r"^\S+ \(([^)]+)\)", Path(path).read_text(errors="replace"))
    if not m:
        raise ValueError("Cannot read the version from {}".format(path))
    return m.group(1)


def write_tree(tree, source, maintainer, packages, version, changes, homepage="",
               copyright_holder="", license_name="GPL-3+"):
    """Create debian/ metadata. packages: list of dicts with Package, Depends,
    Description, install (list of 'src dest'), scripts {name: text}."""
    tree = Path(tree)
    deb = tree / "debian"
    (deb / "source").mkdir(parents=True, exist_ok=True)
    (deb / "source/format").write_text("3.0 (native)\n")
    src = ["Source: " + source, "Section: misc", "Priority: optional", "Maintainer: " + maintainer,
           "Build-Depends: debhelper-compat (= 13)", "Standards-Version: 4.7.0",
           "Rules-Requires-Root: no"]
    if homepage:
        src.append("Homepage: " + homepage)
    stanzas = ["\n".join(src)]
    for p in packages:
        lines = ["Package: " + p["Package"], "Architecture: " + p.get("Architecture", "all"),
                 "Depends: ${misc:Depends}" + (", " + p["Depends"] if p.get("Depends") else "")]
        for key in ("Recommends", "Provides", "Breaks", "Replaces", "Conflicts"):
            if p.get(key):
                lines.append("{}: {}".format(key, p[key]))
        summary, *rest = p["Description"].split("\n")
        lines.append("Description: " + summary)
        lines += [" " + (r if r.strip() else ".") for r in rest]
        stanzas.append("\n".join(lines))
        name = p["Package"]
        (deb / (name + ".install")).write_text("\n".join(p.get("install", [])) + "\n")
        for script, text in p.get("scripts", {}).items():
            f = deb / "{}.{}".format(name, script)
            f.write_text(text)
            f.chmod(0o755)
    (deb / "control").write_text("\n\n".join(stanzas) + "\n")
    cl = deb / "changelog"
    old = cl.read_text() if cl.exists() else ""
    cl.write_text(changelog_entry(source, version, maintainer, changes) + ("\n" + old if old else ""))
    (deb / "copyright").write_text(
        "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n"
        "Upstream-Name: {0}\n\nFiles: *\nCopyright: {1} {2}\nLicense: {3}\n"
        " On Debian systems, the complete text of the license can be found in\n"
        " /usr/share/common-licenses/.\n".format(
            source, datetime.date.today().year, copyright_holder or maintainer, license_name))
    rules = deb / "rules"
    rules.write_text("#!/usr/bin/make -f\n%:\n\tdh $@\n")
    rules.chmod(0o755)
    return tree


def build_tree(tree, out_dir):
    """Build every binary package of *tree* with dpkg-deb. Returns the .deb paths."""
    runner.require("dpkg-deb")
    tree, out_dir = Path(tree), Path(out_dir)
    deb = tree / "debian"
    stanzas = parse_deb822((deb / "control").read_text())
    source, binaries = stanzas[0], stanzas[1:]
    version = changelog_version(deb / "changelog")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for b in binaries:
        name = b["Package"]
        if not NAME_RE.match(name):
            raise ValueError("Invalid package name: {}".format(name))
        stage = tree / "build" / name
        if stage.exists():
            shutil.rmtree(stage)
        (stage / "DEBIAN").mkdir(parents=True)
        install = deb / (name + ".install")
        if not install.exists() and len(binaries) == 1:
            install = deb / "install"
        for line in (install.read_text().splitlines() if install.exists() else []):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            src_path = (tree / parts[0]).resolve()
            if tree.resolve() not in src_path.parents:
                raise ValueError("debian/install path outside the package: {}".format(parts[0]))
            dest = stage / (parts[1].lstrip("/") if len(parts) > 1 else "")
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / src_path.name
            if src_path.is_dir():
                if target.exists():
                    _merge(src_path, target)
                else:
                    shutil.copytree(src_path, target, symlinks=True)
            else:
                shutil.copy2(src_path, target, follow_symlinks=False)
        for script in SCRIPTS:
            for candidate in (deb / "{}.{}".format(name, script), deb / script):
                if candidate.exists():
                    text = candidate.read_text().replace("#DEBHELPER#\n", "")
                    target = stage / "DEBIAN" / script
                    target.write_text(text)
                    target.chmod(0o755 if script not in ("templates", "triggers") else 0o644)
                    break
        conffiles = sorted("/" + str(p.relative_to(stage)) for p in (stage / "etc").rglob("*")
                           if p.is_file() and not p.is_symlink()) if (stage / "etc").exists() else []
        if conffiles:
            (stage / "DEBIAN/conffiles").write_text("\n".join(conffiles) + "\n")
        size = sum(p.stat().st_size for p in stage.rglob("*")
                   if p.is_file() and not p.is_symlink() and "DEBIAN" not in p.parts) // 1024 + 1
        fields = {"Package": name, "Source": source["Source"] if source["Source"] != name else "",
                  "Version": version, "Architecture": b.get("Architecture", "all"),
                  "Maintainer": source.get("Maintainer", ""), "Section": b.get("Section", source.get("Section", "misc")),
                  "Priority": b.get("Priority", source.get("Priority", "optional"))}
        for key in ("Pre-Depends", "Depends", "Recommends", "Suggests", "Conflicts", "Breaks",
                    "Replaces", "Provides"):
            value = re.sub(r"\$\{[^}]+\}\s*,?\s*", "", b.get(key, "")).strip().strip(",").strip()
            if value:
                fields[key] = value
        if source.get("Homepage"):
            fields["Homepage"] = source["Homepage"]
        fields["Installed-Size"] = str(size)
        desc = b.get("Description", name)
        lines = []
        for key in BINARY_FIELDS + ["Installed-Size"]:
            if key == "Description" or not fields.get(key):
                continue
            lines.append("{}: {}".format(key, fields[key]))
        first, *rest = desc.split("\n")
        lines.append("Description: " + first)
        lines += [" " + (r if r.strip() else ".") for r in rest]
        (stage / "DEBIAN/control").write_text("\n".join(lines) + "\n")
        for p in stage.rglob("*"):
            if p.is_dir() and not p.is_symlink():
                p.chmod(0o755)
        out = out_dir / "{}_{}_{}.deb".format(name, version.split(":")[-1], fields["Architecture"])
        log.info("Building %s", out.name)
        runner.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", stage, out], quiet=True)
        results.append(out)
    shutil.rmtree(tree / "build", ignore_errors=True)
    return results


def _merge(src, dst):
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir() and not item.is_symlink():
            target.mkdir(exist_ok=True)
            _merge(item, target)
        else:
            shutil.copy2(item, target, follow_symlinks=False)


def bump_version(version, tag):
    """1.0+mylinux3 -> 1.0+mylinux4 ; 1.0 -> 1.0+mylinux1"""
    m = re.match(r"^(.*\+{})(\d+)$".format(re.escape(tag)), version)
    if m:
        return "{}{}".format(m.group(1), int(m.group(2)) + 1)
    return "{}+{}1".format(version, tag)
