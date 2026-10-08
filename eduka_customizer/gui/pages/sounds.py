"""System Sounds page: sounds for boot, login, logout, shutdown, errors,
notifications and devices, made the default of every desktop."""

import shutil
import subprocess
from pathlib import Path

from eduka_customizer.qt.widgets import QCheckBox, QFileDialog, QGridLayout, QLabel, QLineEdit, QMessageBox

from eduka_customizer.core import sounds
from eduka_customizer.gui.widgets import DropZone, Page, button, combo, hbox, label

AUDIO_FILTER = "Sounds (*.oga *.ogg *.wav *.flac *.mp3 *.m4a *.opus);;All files (*)"


def play_on_host(path):
    """Preview a sound on this computer (best effort)."""
    for cmd in (["pw-play"], ["paplay"], ["ogg123", "-q"], ["aplay", "-q"]):
        exe = shutil.which(cmd[0])
        if exe and not (cmd[0] == "aplay" and not str(path).endswith(".wav")):
            subprocess.Popen([exe] + cmd[1:] + [str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
    return False


class SoundsPage(Page):
    title = "System Sounds"
    nav_title = "System Sounds"
    subtitle = ("Step 9 · Sounds for start-up, login, log out, shutdown, errors, notifications and devices. "
                "They become the default sounds of every desktop. Your changes wait in Review & Apply (step 12).")
    icon_names = ("preferences-desktop-sound", "audio-volume-high", "multimedia-volume-control")
    CHANGES = ('Apply system sounds', 'Remove system sounds', 'Sound theme ')

    def build(self):
        c = self.card("Sound theme", "Your own theme inherits the freedesktop theme: events without a sound of "
                                     "yours keep the standard one.")
        f = c.form()
        self.theme = QLineEdit()
        self.theme.setPlaceholderText("theme folder name, e.g. mylinux")
        f.addRow("Theme name:", self.theme)
        self.installed = combo([])
        f.addRow("Or use an installed theme:", hbox(self.installed, button("Use it", self.use_installed)))
        drop = DropZone("Drop sound files or a folder here (OGG, WAV, FLAC, MP3). Names such as boot.ogg, "
                        "login.wav, shutdown.ogg, error.oga or notification.ogg are matched to their event "
                        "automatically.", AUDIO_FILTER)
        drop.dropped.connect(self.add_paths)
        c.add(drop)

        c = self.card("Sounds", "Choose a sound for each event, play it here, or clear it.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.rows = {}
        group = None
        row = 0
        for ev, text, grp, _std in sounds.EVENTS:
            if grp != group:
                grid.addWidget(label(grp, "cardTitle"), row, 0, 1, 5)
                row += 1
                group = grp
            name = QLabel("—")
            name.setObjectName("muted")
            grid.addWidget(QLabel(text), row, 0)
            grid.addWidget(name, row, 1)
            grid.addWidget(button("Choose...", lambda _c=False, e=ev: self.choose(e)), row, 2)
            grid.addWidget(button("▶ Play", lambda _c=False, e=ev: self.play(e)), row, 3)
            grid.addWidget(button("Clear", lambda _c=False, e=ev: self.clear(e)), row, 4)
            self.rows[ev] = name
            row += 1
        grid.setColumnStretch(1, 1)
        c.add(grid)

        c = self.card("When the sounds play")
        self.boot = QCheckBox("Boot sound when the computer starts (systemd service, needs alsa-utils)")
        self.login = QCheckBox("Startup sound when a user logs in (autostart)")
        self.shutdown = QCheckBox("Shutdown sound when the computer stops")
        self.events = QCheckBox("Event sounds: errors, warnings, notifications, devices (played by the desktop)")
        for w in (self.boot, self.login, self.shutdown, self.events):
            w.setChecked(True)
            c.add(w)
        self.state_label = label("", "muted")
        c.add(self.state_label)
        c.add(hbox(button("Remove system sounds", self.remove, "danger"), None,
                   button("Apply to the image", self.apply, "primary")))

    # Helpers ----------------------------------------------------------------------
    def _sounds(self):
        if self.theme.text().strip():
            self.project.state.setdefault("sounds", {})["theme"] = self.theme.text().strip()
        return sounds.Sounds(self.project)

    def refresh(self):
        if not self.project:
            return
        s = sounds.Sounds(self.project)
        st = s.state()
        self.theme.setText(st["theme"])
        self.installed.clear()
        for tid, name in sounds.installed_themes(self.project.rootfs):
            self.installed.addItem("{} ({})".format(name, tid), tid)
        for ev, lab in self.rows.items():
            f = st["files"].get(ev)
            lab.setText(Path(f).name if f else "— standard sound —")
        self.boot.setChecked(bool(st.get("boot", True)) or "sounds" not in self.project.state)
        self.login.setChecked(bool(st.get("login", True)) or "sounds" not in self.project.state)
        self.shutdown.setChecked(bool(st.get("shutdown", True)) or "sounds" not in self.project.state)
        self.events.setChecked(bool(st.get("event_sounds", True)))
        self.state_label.setText("{} sound(s) of your own in /usr/share/sounds/{}".format(len(st["files"]),
                                                                                        st["theme"]))

    # Actions ----------------------------------------------------------------------
    def choose(self, ev):
        path, _ = QFileDialog.getOpenFileName(self, "Sound for " + sounds.event(ev)[1], "", AUDIO_FILTER)
        if path:
            try:
                self._sounds().set_sound(ev, path)
            except ValueError as e:
                QMessageBox.warning(self, "System Sounds", str(e))
            self.refresh()

    def add_paths(self, paths):
        s = self._sounds()
        added, unknown, errors = {}, [], []
        for p in paths:
            p = Path(p)
            try:
                if p.is_dir():
                    added.update(s.add_folder(p))
                else:
                    ev = sounds.match_event(p.name)
                    if ev:
                        s.set_sound(ev, p)
                        added[ev] = p.name
                    else:
                        unknown.append(p.name)
            except ValueError as e:
                errors.append(str(e))
        self.refresh()
        msg = "Added: {}".format(", ".join("{} → {}".format(f, sounds.event(e)[1]) for e, f in added.items()) or
                                 "nothing")
        if unknown:
            msg += "\n\nNot recognized (use Choose... next to the event): " + ", ".join(unknown)
        if errors:
            msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "System Sounds", msg)

    def play(self, ev):
        f = sounds.Sounds(self.project).files().get(ev)
        if not f:
            self.main.stage_label.setText("No sound of your own for this event")
        elif not play_on_host(f):
            self.main.stage_label.setText("No sound player on this computer (pw-play, paplay, ogg123 or aplay)")

    def clear(self, ev):
        self._sounds().remove_sound(ev)
        self.refresh()

    def use_installed(self):
        tid = self.installed.currentData()
        if tid:
            proj, boot, login, down, ev = (self.project, self.boot.isChecked(), self.login.isChecked(),
                                           self.shutdown.isChecked(), self.events.isChecked())
            self.task("Sound theme " + tid, lambda t: sounds.Sounds(proj).apply(tid, boot, login, down, ev),
                      lambda _r: self.refresh())

    def apply(self):
        s = self._sounds()
        theme = s.theme_id()
        proj, boot, login, down, ev = (self.project, self.boot.isChecked(), self.login.isChecked(),
                                       self.shutdown.isChecked(), self.events.isChecked())
        self.task("Apply system sounds", lambda t: sounds.Sounds(proj).apply(theme, boot, login, down, ev),
                  lambda _r: self.refresh())

    def remove(self):
        if QMessageBox.question(self, "System Sounds", "Remove your sound theme and the boot, login and shutdown "
                                "sounds from the image?") == QMessageBox.StandardButton.Yes:
            proj = self.project
            self.task("Remove system sounds", lambda t: sounds.Sounds(proj).remove(), lambda _r: self.refresh())
