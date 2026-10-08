"""System-wide gsettings defaults (GNOME, Cinnamon, MATE, Budgie, ...).

Defaults are written as a .gschema.override file. Only schemas and keys that
exist in the image are written, so glib-compile-schemas never stumbles over a
desktop that is not installed.
"""

import re
from pathlib import Path

from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

SCHEMAS = "usr/share/glib-2.0/schemas"


def known_keys(rootfs):
    """{schema id: {key names}} of the schemas installed in the image."""
    out = {}
    d = Path(rootfs, SCHEMAS)
    if not d.is_dir():
        return out
    for xml in d.glob("*.gschema.xml"):
        try:
            text = xml.read_text(errors="replace")
        except OSError:
            continue
        for m in re.finditer(r'<schema\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</schema>', text, re.S):
            out.setdefault(m.group(1), set()).update(re.findall(r'<key\b[^>]*\bname="([^"]+)"', m.group(2)))
    return out


def gvariant(value):
    """Python value -> GVariant text for an override file."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(gvariant(v) for v in value) + "]"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def write_override(rootfs, name, values, compile_=True):
    """Write /usr/share/glib-2.0/schemas/<name>.gschema.override.

    values: {schema: {key: python value}}. Returns the {schema: [keys]} written;
    an empty result removes the file."""
    keys = known_keys(rootfs)
    blocks, written = [], {}
    for schema, kv in values.items():
        have = keys.get(schema)
        if have is None:
            continue
        lines = ["{}={}".format(k, gvariant(v)) for k, v in kv.items() if k in have]
        if lines:
            blocks.append("[{}]\n{}".format(schema, "\n".join(lines)))
            written[schema] = [k for k in kv if k in have]
    path = Path(rootfs, SCHEMAS, name + ".gschema.override")
    if blocks:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n".join(blocks) + "\n")
    elif path.exists():
        path.unlink()
    if compile_:
        compile_schemas(rootfs)
    return written


def compile_schemas(rootfs):
    if Path(rootfs, "usr/bin/glib-compile-schemas").exists():
        rc = Chroot(rootfs).run(["glib-compile-schemas", "/" + SCHEMAS], check=False, quiet=True)
        if rc:
            log.warning("glib-compile-schemas reported a problem (exit %s)", rc)
