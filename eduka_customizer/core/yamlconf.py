"""Edit top-level keys of YAML configuration files and keep everything else.

Calamares' configuration files are full of helpful comments. Re-dumping the
whole document with PyYAML would drop them, so only the block of the key
that changes is rewritten.
"""

import re

import yaml


def load(text):
    try:
        data = yaml.safe_load(text) if text.strip() else {}
    except yaml.YAMLError as e:
        raise ValueError("Invalid YAML: {}".format(e))
    return data if isinstance(data, dict) else {}


def dump_value(key, value):
    return yaml.safe_dump({key: value}, default_flow_style=False, sort_keys=False,
                          allow_unicode=True, width=100)


def _block(lines, key):
    """Return (start, end) of the top-level block of *key*, or None.

    Comment lines (even at column 0, as in Debian's branding.desc) do not end
    a block; trailing blank lines and comments stay outside it.
    """
    pat = re.compile(r"^{}\s*:".format(re.escape(key)))
    for i, line in enumerate(lines):
        if pat.match(line):
            end = last = i + 1
            while end < len(lines):
                nxt = lines[end]
                if nxt.strip() == "" or nxt.lstrip().startswith("#"):
                    end += 1
                    continue
                if nxt[:1] in (" ", "\t") or nxt.startswith("- "):
                    end += 1
                    last = end
                    continue
                break
            return i, last
    return None


def set_key(text, key, value):
    """Set top-level *key* to *value*; None removes the key."""
    lines = text.splitlines()
    span = _block(lines, key)
    new = [] if value is None else dump_value(key, value).rstrip("\n").splitlines()
    if span:
        # Comments inside the old block (e.g. disabled options) are kept below it.
        kept = [l for l in lines[span[0] + 1:span[1]] if l.lstrip().startswith("#")]
        lines[span[0]:span[1]] = new + kept
    elif new:
        if lines and lines[-1].strip():
            lines.append("")
        lines += new
    out = "\n".join(lines) + "\n"
    load(out)  # never write a file Calamares cannot read
    return out


def update(text, values):
    for key, value in values.items():
        text = set_key(text, key, value)
    return text
