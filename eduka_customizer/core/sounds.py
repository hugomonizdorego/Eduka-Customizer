"""System sounds: boot, login, logout, shutdown, errors, notifications, devices.

The sounds become a freedesktop.org sound theme (/usr/share/sounds/<id>/) that
inherits 'freedesktop', and that theme is made the default of every desktop
(GNOME, Cinnamon, MATE, Budgie: gsettings; Xfce: xsettings; KDE: plasmarc; all
GTK applications: settings.ini). Desktops and applications play the event
sounds themselves. Three sounds no desktop plays on its own are added:

* boot     -- a systemd service plays it when the sound card is ready;
* login    -- an autostart entry plays it when a user session starts;
* shutdown -- the same systemd service plays it when the computer stops.
"""

import re
import shutil
import subprocess
from pathlib import Path

from eduka_customizer.core import gsettings
from eduka_customizer.core.log import log
from eduka_customizer.core.themes import _ini, _xml_prop

# (event id, label, group, freedesktop sound name)
EVENTS = [
    ("system-bootup", "Boot (computer starts)", "System", True),
    ("desktop-login", "Startup (user logs in)", "System", True),
    ("desktop-logout", "Log out", "System", True),
    ("system-shutdown", "Shutdown", "System", True),
    ("dialog-error", "Error", "Dialogs", True),
    ("dialog-warning", "Warning", "Dialogs", True),
    ("dialog-information", "Information", "Dialogs", True),
    ("dialog-question", "Question", "Dialogs", True),
    ("message-new-instant", "New message / notification", "Messages", True),
    ("message-new-email", "New e-mail", "Messages", True),
    ("complete", "Task complete (download, copy)", "Messages", True),
    ("bell", "Bell (terminal, alert)", "Messages", True),
    ("device-added", "Device connected (USB)", "Devices", True),
    ("device-removed", "Device removed", "Devices", True),
    ("power-plug", "Power cable plugged in", "Power", True),
    ("power-unplug", "Power cable unplugged", "Power", True),
    ("battery-low", "Battery low", "Power", True),
    ("trash-empty", "Trash emptied", "Desktop", True),
    ("screen-capture", "Screenshot", "Desktop", True),
    ("audio-volume-change", "Volume changed", "Desktop", True),
    ("camera-shutter", "Camera shutter", "Desktop", True),
]
EVENT_IDS = [e[0] for e in EVENTS]
# Names people give their files, matched when a folder is dropped.
ALIASES = {
    "system-bootup": ("boot", "bootup", "startup-system", "system-start", "power-on"),
    "desktop-login": ("login", "startup", "start", "welcome", "logon", "session-start"),
    "desktop-logout": ("logout", "logoff", "session-end"),
    "system-shutdown": ("shutdown", "poweroff", "power-off", "halt"),
    "dialog-error": ("error", "critical", "fail"),
    "dialog-warning": ("warning", "warn"),
    "dialog-information": ("information", "info"),
    "dialog-question": ("question",),
    "message-new-instant": ("message", "notification", "notify"),
    "message-new-email": ("email", "mail"),
    "complete": ("complete", "done", "finished"),
    "bell": ("bell", "beep", "alert"),
    "device-added": ("device-added", "plug", "usb-in", "connect"),
    "device-removed": ("device-removed", "unplug", "usb-out", "disconnect"),
    "power-plug": ("power-plug", "charger-in"),
    "power-unplug": ("power-unplug", "charger-out"),
    "battery-low": ("battery-low", "battery"),
    "trash-empty": ("trash-empty", "trash"),
    "screen-capture": ("screen-capture", "screenshot"),
    "audio-volume-change": ("audio-volume-change", "volume"),
    "camera-shutter": ("camera-shutter", "camera", "shutter"),
}
# Formats every sound theme player (libcanberra) understands; others are converted.
NATIVE = (".oga", ".ogg", ".wav")
CONVERT = (".mp3", ".flac", ".m4a", ".aac", ".opus", ".wma")
LIB = "usr/lib/eduka-customizer-sounds"
PLAYER = LIB + "/play-sound"
UNIT = "etc/systemd/system/eduka-system-sounds.service"
AUTOSTART = "etc/xdg/autostart/eduka-login-sound.desktop"
OVERRIDE = "92_eduka-sounds"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,40}$")

PLAYER_SH = """#!/bin/sh
# Plays one event of the system sound theme (Eduka-Customizer).
# Usage: play-sound EVENT   e.g. play-sound system-bootup
THEME="$(cat /usr/lib/eduka-customizer-sounds/theme 2>/dev/null)"
[ -n "$THEME" ] || exit 0
f=""
for ext in oga ogg wav; do
    if [ -f "/usr/share/sounds/$THEME/stereo/$1.$ext" ]; then f="/usr/share/sounds/$THEME/stereo/$1.$ext"; break; fi
done
[ -n "$f" ] || exit 0
if [ -n "$XDG_RUNTIME_DIR" ]; then
    # Inside a user session: the sound server (PipeWire or PulseAudio).
    command -v pw-play >/dev/null 2>&1 && pw-play "$f" 2>/dev/null && exit 0
    command -v paplay >/dev/null 2>&1 && paplay "$f" 2>/dev/null && exit 0
    command -v canberra-gtk-play >/dev/null 2>&1 && canberra-gtk-play -f "$f" 2>/dev/null && exit 0
fi
# At boot and shutdown: straight to the sound card.
case "$f" in
    *.wav) command -v aplay >/dev/null 2>&1 && exec aplay -q "$f" ;;
esac
command -v ogg123 >/dev/null 2>&1 && exec ogg123 -q "$f"
command -v aplay >/dev/null 2>&1 && exec aplay -q "$f"
exit 0
"""

UNIT_TEXT = """[Unit]
Description=System sounds at boot and shutdown
After=sound.target alsa-restore.service alsa-state.service
Wants=sound.target
ConditionPathExists=/usr/lib/eduka-customizer-sounds/play-sound

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={start}
ExecStop={stop}
TimeoutStopSec=8

[Install]
WantedBy=multi-user.target
"""

AUTOSTART_TEXT = """[Desktop Entry]
Type=Application
Name=Login sound
Comment=Plays the login sound of the system sound theme
Exec=/usr/lib/eduka-customizer-sounds/play-sound desktop-login
NoDisplay=true
NotShowIn=X-Cinnamon;
X-GNOME-Autostart-Phase=Application
X-GNOME-Autostart-enabled=true
"""


def event(event_id):
    for e in EVENTS:
        if e[0] == event_id:
            return e
    raise KeyError("Unknown sound event: {} (see 'sounds events')".format(event_id))


def sniff(path):
    """'ogg', 'wav', 'flac', 'mp3' or '' from the first bytes of a file."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(12)
    except OSError:
        return ""
    if head.startswith(b"OggS"):
        return "ogg"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "wav"
    if head.startswith(b"fLaC"):
        return "flac"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if head[4:8] == b"ftyp":
        return "m4a"
    return ""


def match_event(filename):
    """Guess the event of a sound file from its name (login.ogg -> desktop-login)."""
    stem = Path(filename).stem.lower().replace("_", "-").replace(" ", "-")
    if stem in EVENT_IDS:
        return stem
    for ev, names in ALIASES.items():
        if stem in names:
            return ev
    words = set(stem.split("-"))
    for ev, names in ALIASES.items():
        if any((n in words) if "-" not in n else (n in stem) for n in names if len(n) > 3):
            return ev
    return None


def installed_themes(rootfs):
    d = Path(rootfs, "usr/share/sounds")
    if not d.is_dir():
        return []
    out = []
    for idx in sorted(d.glob("*/index.theme")):
        m = re.search(r"(?m)^Name=(.*)$", idx.read_text(errors="replace"))
        out.append((idx.parent.name, m.group(1).strip() if m else idx.parent.name))
    return out


class Sounds:
    def __init__(self, project):
        self.project = project
        self.rootfs = Path(project.rootfs)

    # State -----------------------------------------------------------------
    def theme_id(self):
        st = self.project.state.get("sounds", {})
        return st.get("theme") or self.project.os_id()

    def theme_dir(self, theme=None):
        return self.rootfs / "usr/share/sounds" / (theme or self.theme_id()) / "stereo"

    def files(self, theme=None):
        """{event: path in the image} of the theme."""
        d = self.theme_dir(theme)
        out = {}
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.suffix in NATIVE and f.stem in EVENT_IDS:
                    out[f.stem] = f
        return out

    def state(self):
        st = dict(self.project.state.get("sounds", {}))
        st.setdefault("theme", self.theme_id())
        st.setdefault("boot", (self.rootfs / UNIT).exists())
        st.setdefault("login", (self.rootfs / AUTOSTART).exists())
        st.setdefault("shutdown", (self.rootfs / UNIT).exists())
        st["files"] = {k: str(v) for k, v in self.files(st["theme"]).items()}
        return st

    # Files -----------------------------------------------------------------
    def set_sound(self, event_id, source):
        """Copy *source* into the theme as the sound of *event_id*."""
        event(event_id)
        source = Path(source)
        kind = sniff(source)
        if not kind:
            raise ValueError("{} is not a sound file (use OGG, WAV, FLAC or MP3)".format(source.name))
        d = self.theme_dir()
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob(event_id + ".*"):
            old.unlink()
        if kind in ("ogg", "wav"):
            dest = d / (event_id + (".oga" if kind == "ogg" else ".wav"))
            shutil.copy2(source, dest)
        else:
            dest = d / (event_id + ".oga")
            self._convert(source, dest)
        dest.chmod(0o644)
        self._write_index()
        log.info("Sound for %s: %s", event_id, source.name)
        return dest

    def _convert(self, source, dest):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise ValueError("{} needs converting to OGG: install ffmpeg on this computer, or use an OGG or WAV "
                             "file".format(source.name))
        res = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(source), "-vn", "-c:a", "libvorbis", "-q:a",
                              "5", "-f", "ogg", str(dest)], capture_output=True, text=True)
        if res.returncode or not dest.exists():
            raise ValueError("Could not convert {}: {}".format(source.name, res.stderr.strip()[-300:]))

    def remove_sound(self, event_id):
        for old in self.theme_dir().glob(event_id + ".*"):
            old.unlink()

    def add_folder(self, folder):
        """Add every sound of a folder whose name says its event. Returns {event: file name}."""
        found = {}
        for f in sorted(Path(folder).rglob("*")):
            if f.is_file() and f.suffix.lower() in NATIVE + CONVERT:
                ev = match_event(f.name)
                if ev and ev not in found:
                    self.set_sound(ev, f)
                    found[ev] = f.name
        return found

    def _write_index(self):
        d = self.theme_dir().parent
        name = self.project.display_name()
        (d / "index.theme").write_text(
            "[Sound Theme]\nName={}\nComment=System sounds of {}\nInherits=freedesktop\nDirectories=stereo\n\n"
            "[stereo]\nOutputProfile=stereo\n".format(name, name))

    # Apply -----------------------------------------------------------------
    def apply(self, theme=None, boot=True, login=True, shutdown=True, event_sounds=True):
        """Make the theme the default everywhere and enable the boot/login/shutdown sounds."""
        theme = theme or self.theme_id()
        if not SAFE_ID.match(theme):
            raise ValueError("Invalid sound theme name: {}".format(theme))
        if not (self.rootfs / "usr/share/sounds" / theme / "index.theme").exists():
            if theme == self.theme_id() and self.files(theme):
                self._write_index()
            else:
                raise FileNotFoundError("Sound theme {} is not in the image: add sounds first".format(theme))
        r = self.rootfs
        files = self.files(theme)
        packages = [p for p in ("sound-theme-freedesktop",) if not self._has(p)]
        if (boot and "system-bootup" in files) or (shutdown and "system-shutdown" in files):
            packages += [p for p in ("alsa-utils", "vorbis-tools") if not self._has(p)]
        if packages:
            from eduka_customizer.core.apt import Packages
            pk = Packages(self.project)
            with pk.chroot:
                ok = pk.available(packages)
                if ok:
                    pk.install([p for p in packages if p in ok])
        # Player and default theme name
        (r / LIB).mkdir(parents=True, exist_ok=True)
        (r / PLAYER).write_text(PLAYER_SH)
        (r / PLAYER).chmod(0o755)
        (r / LIB / "theme").write_text(theme + "\n")
        # Desktops

        def rel(ev):
            return "/" + str(files[ev].relative_to(r)) if ev in files else ""
        login_file, logout_file = rel("desktop-login"), rel("desktop-logout")
        cin = {"login-enabled": bool(login and login_file), "logout-enabled": bool(logout_file)}
        if login_file:
            cin["login-file"] = login_file
        if logout_file:
            cin["logout-file"] = logout_file
        for ev, key in (("message-new-instant", "notification"), ("device-added", "plug"),
                        ("device-removed", "unplug")):
            if ev in files:
                cin[key + "-enabled"] = True
                cin[key + "-file"] = rel(ev)
        gsettings.write_override(r, OVERRIDE, {
            "org.gnome.desktop.sound": {"theme-name": theme, "event-sounds": bool(event_sounds)},
            "org.mate.sound": {"theme-name": theme, "event-sounds": bool(event_sounds)},
            "org.cinnamon.desktop.sound": {"theme-name": theme, "event-sounds": bool(event_sounds)},
            "org.cinnamon.sounds": cin,
        })
        for rel_ in ("etc/gtk-3.0/settings.ini", "etc/gtk-4.0/settings.ini"):
            _ini(r / rel_, "Settings", {"gtk-sound-theme-name": theme,
                                        "gtk-enable-event-sounds": "1" if event_sounds else "0"})
        xs = r / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
        _xml_prop(xs, "SoundThemeName", theme)
        _xml_prop(xs, "EnableEventSounds", "true" if event_sounds else "false")
        _ini(r / "etc/xdg/plasmarc", "Sounds", {"Theme": theme})
        # Boot / shutdown service and login autostart
        unit, wants = r / UNIT, r / "etc/systemd/system/multi-user.target.wants/eduka-system-sounds.service"
        use_boot, use_down = boot and "system-bootup" in files, shutdown and "system-shutdown" in files
        if use_boot or use_down:
            unit.parent.mkdir(parents=True, exist_ok=True)
            unit.write_text(UNIT_TEXT.format(
                start="/" + PLAYER + " system-bootup" if use_boot else "/bin/true",
                stop="/" + PLAYER + " system-shutdown" if use_down else "/bin/true"))
            wants.parent.mkdir(parents=True, exist_ok=True)
            if wants.is_symlink() or wants.exists():
                wants.unlink()
            wants.symlink_to("/" + UNIT)
        else:
            for p in (unit, wants):
                if p.is_symlink() or p.exists():
                    p.unlink()
        auto = r / AUTOSTART
        if login and "desktop-login" in files:
            auto.parent.mkdir(parents=True, exist_ok=True)
            auto.write_text(AUTOSTART_TEXT)
        elif auto.exists():
            auto.unlink()
        self.project.state["sounds"] = {"theme": theme, "boot": bool(use_boot), "login": bool(login),
                                        "shutdown": bool(use_down), "event_sounds": bool(event_sounds)}
        self.project.save()
        self.project.record("sounds", "{} ({} sounds)".format(theme, len(files)))
        log.info("System sound theme: %s (%d sounds)", theme, len(files))

    def remove(self):
        """Remove the system sounds: back to the desktop's own sounds."""
        r = self.rootfs
        theme = self.theme_id()
        for p in (r / UNIT, r / "etc/systemd/system/multi-user.target.wants/eduka-system-sounds.service",
                  r / AUTOSTART):
            if p.is_symlink() or p.exists():
                p.unlink()
        if (r / LIB).exists():
            shutil.rmtree(r / LIB)
        if (r / "usr/share/sounds" / theme).is_dir():
            shutil.rmtree(r / "usr/share/sounds" / theme)
        gsettings.write_override(r, OVERRIDE, {})
        for rel_ in ("etc/gtk-3.0/settings.ini", "etc/gtk-4.0/settings.ini"):
            p = r / rel_
            if p.exists():
                p.write_text(re.sub(r"(?m)^gtk-(sound-theme-name|enable-event-sounds)=.*\n", "", p.read_text()))
        self.project.state.pop("sounds", None)
        self.project.save()
        self.project.record("sounds", "removed")

    def _has(self, package):
        status = self.rootfs / "var/lib/dpkg/status"
        if not status.exists():
            return False
        return bool(re.search(r"(?ms)^Package: {}\n(?:[^\n]+\n)*?Status: \S+ ok installed".format(re.escape(package)),
                              status.read_text(errors="replace")))
