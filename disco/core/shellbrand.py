"""Terminal branding: the message after login (MOTD) and the bash prompt (PS1).

MOTD: a fixed text in /etc/motd, or a small script in /etc/update-motd.d that
shows the system's name, version, the computer name and the time it is up each
time someone logs in (pam_motd runs these scripts on Debian and Devuan).

PS1: the prompt of bash for every user: /etc/bash.bashrc (all users) and
/etc/skel/.bashrc (the users made after this). Your own prompt or a preset.
"""

import re
from pathlib import Path

from disco.core.log import log

MOTD_SCRIPT = "etc/update-motd.d/05-disco-welcome"
BEGIN = "# >>> D!sco prompt >>>"
END = "# <<< D!sco prompt <<<"
# id: (name, PS1)
PROMPTS = {
    "debian": ("Debian's own (user@host:dir$)", r'\u@\h:\w\$ '),
    "color": ("Colored user@host and folder",
              r'\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '),
    "brand": ("Your distribution's name first",
              r'\[\e[1;35m\]({name})\[\e[0m\] \[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '),
    "twoline": ("Two lines: where you are, then the prompt",
                r'\[\e[1;36m\]┌─[\u@\h]─[\w]\[\e[0m\]\n\[\e[1;36m\]└─\$\[\e[0m\] '),
    "minimal": ("Minimal: only the folder", r'\[\e[1;34m\]\W\[\e[0m\] ❯ '),
}
MOTD_TEMPLATE = """#!/bin/sh
# Shown after login (written by D!sco). Change it in D!sco or edit this file.
. /etc/os-release 2>/dev/null
up=$(uptime -p 2>/dev/null || true)
printf '\\n  Welcome to %s\\n' "${{PRETTY_NAME:-{name}}}"
printf '  Computer: %s   %s\\n' "$(hostname)" "$up"
{extra}printf '\\n'
"""


def _safe_text(text):
    """Text for a shell printf line: no quotes or backslashes that could break the script."""
    return re.sub(r"['\\\\`$]", "", text)


def set_motd(project, text, dynamic=False):
    """The message after login. *dynamic*: also the live line with name, computer and uptime."""
    r = Path(project.rootfs)
    motd = r / "etc/motd"
    motd.parent.mkdir(parents=True, exist_ok=True)
    if motd.is_symlink():
        motd.unlink()
    script = r / MOTD_SCRIPT
    if dynamic:
        extra = "".join("printf '  %s\\n' '{}'\n".format(_safe_text(l)) for l in text.splitlines() if l.strip())
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(MOTD_TEMPLATE.format(name=_safe_text(project.display_name()), extra=extra))
        script.chmod(0o755)
        motd.write_text("")
    else:
        if script.exists():
            script.unlink()
        motd.write_text(text if text.endswith("\n") else text + "\n")
    project.state.setdefault("shell", {}).update({"motd": text, "motd_dynamic": bool(dynamic)})
    project.save()
    project.record("motd", "dynamic" if dynamic else "static")
    log.info("Message of the day set (%s)", "dynamic" if dynamic else "static")


def prompt_text(preset, project=None, custom=""):
    if preset == "custom":
        ps1 = custom
    else:
        if preset not in PROMPTS:
            raise ValueError("Unknown prompt: {}".format(preset))
        ps1 = PROMPTS[preset][1]
        if "{name}" in ps1:
            name = re.sub(r"[^A-Za-z0-9 ._+-]", "", project.display_name() if project else "Linux") or "Linux"
            ps1 = ps1.replace("{name}", name)
    if "'" in ps1 or "\n" in ps1 or len(ps1) > 300:
        raise ValueError("The prompt must be one line without single quotes (300 characters at most)")
    return ps1


def _block(ps1):
    return ("{begin}\n# Every new interactive bash gets this prompt (D!sco). Remove the block to go back.\n"
            "if [ -n \"$PS1\" ]; then\n    PS1='{ps1}'\nfi\n{end}\n").format(begin=BEGIN, ps1=ps1, end=END)


def _put(path, block):
    text = path.read_text(errors="replace") if path.exists() else ""
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
    text = pattern.sub("", text).rstrip("\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((text + "\n\n" if text else "") + block)


def set_prompt(project, preset="color", custom=""):
    """The bash prompt for all users (/etc/bash.bashrc) and new users (/etc/skel/.bashrc)."""
    ps1 = prompt_text(preset, project, custom)
    r = Path(project.rootfs)
    block = _block(ps1)
    _put(r / "etc/bash.bashrc", block)
    skel = r / "etc/skel/.bashrc"
    if skel.exists():
        # Debian's .bashrc sets its own PS1 (and color_prompt): ours comes after it.
        _put(skel, block)
    project.state.setdefault("shell", {}).update({"prompt": preset, "prompt_custom": custom})
    project.save()
    project.record("prompt", preset)
    return ps1


def remove_prompt(project):
    r = Path(project.rootfs)
    for p in (r / "etc/bash.bashrc", r / "etc/skel/.bashrc"):
        if p.exists():
            pattern = re.compile(r"\n*" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
            p.write_text(pattern.sub("\n", p.read_text(errors="replace")).rstrip("\n") + "\n")
    project.state.setdefault("shell", {}).pop("prompt", None)
    project.save()
