"""Welcome: the first page of D!sco (what it does, how it works, support, show at start)."""

from disco import APP_NAME, AUTHOR, DONATE_URL, FACEBOOK_URL, HOMEPAGE, LICENSE, VERSION_LABEL
from disco.qt.core import Qt
from disco.qt.gui import QPixmap
from disco.qt.widgets import QCheckBox, QLabel

from disco.core.config import settings
from disco.gui.opener import open_url
from disco.gui.widgets import Page, button, hbox, label

STEPS = [
    ("1", "Start", "Extract a Debian or Debian-based live ISO, or continue a project."),
    ("2–9", "Customize", "System, software, startup, branding, look, boot, installer and files: change what you "
                         "like, skip the rest with Next."),
    ("10", "Review & Apply", "Check the list of your changes and apply them all at once."),
    ("11", "Build", "Press Finish: D!sco checks the system and makes your ISO."),
]


def show_at_start():
    cfg = settings()
    return cfg.get("general", "show_welcome").strip().lower() not in ("no", "false", "0")


class HomePage(Page):
    title = "Welcome to D!sco"
    nav_title = "Welcome"
    subtitle = ("D!sco (Distro Custom) makes your own Linux distribution from a Debian or Devuan live ISO, step by "
                "step: open the ISO, change what you like, press Finish.")
    icon_names = ("go-home", "user-home")
    needs_rootfs = False

    def build(self):
        from disco.core.config import data_file
        head = self.card()
        logo = QLabel()
        pix = QPixmap(str(data_file("icons", "disco.svg")))
        if pix.isNull():
            pix = QPixmap(str(data_file("..", "icons", "disco.svg")))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        intro = label("<span style='font-size:20pt; font-weight:600'>{} {}</span><br>"
                      "<span style='font-size:12pt'>Distro Custom</span><br><br>"
                      "Easy for beginners, complete for experts: every part of the distribution can be changed "
                      "in a window, as files in folders of yours, or in a terminal inside the system. Debian's "
                      "own tools are used (live-boot, squashfs, xorriso, Calamares); nothing of Ubuntu.".format(
                          APP_NAME, VERSION_LABEL))
        head.add(hbox(logo, intro))

        how = self.card("How it works")
        for num, name, text in STEPS:
            how.add(label("<b>{}</b> &nbsp; <b>{}</b> — {}".format(num, name, text)))
        how.add(label("Every step has <b>Back</b> and <b>Next</b> at the bottom. Your work is saved in the project "
                      "folder: close D!sco at any time and continue later from Start.", "muted"))

        rec = self.card("Recommended")
        rec.add(label("• <b>An internet connection</b>: installing packages, desktops, Flatpak applications and "
                      "kernels needs it (extracting and editing work offline).<br>"
                      "• Debian 12 or newer (or a Debian-based system) on this computer, 4 GB of memory and about "
                      "20 GB of free disk space.<br>"
                      "• To start: the small <b>Debian live standard ISO</b> (no desktop), then add the desktop you "
                      "want in step 3."))

        sup = self.card("About and support")
        sup.add(label("{} is free software ({}), made by {} and contributors. If it helps you, a donation keeps "
                      "it going.".format(APP_NAME, LICENSE, AUTHOR)))
        sup.add(hbox(button("♥  Donate with PayPal", lambda: open_url(DONATE_URL), "primary"),
                     button("Facebook", lambda: open_url(FACEBOOK_URL)),
                     button("Project page", lambda: open_url(HOMEPAGE)),
                     button("User guide (PDF)", self.guide), None))

        self.show_check = QCheckBox("Show this page when D!sco starts")
        self.show_check.setChecked(show_at_start())
        self.show_check.toggled.connect(self._toggle)
        self.add(hbox(self.show_check, None, button("Get started  ▶", self.start, "primary")))

    def _toggle(self, on):
        cfg = settings()
        cfg.set("general", "show_welcome", "yes" if on else "no")
        try:
            cfg.save()
        except OSError as e:
            self.main.stage_label.setText("Could not save the setting: {}".format(e))

    def start(self):
        self.main.go("ProjectPage")

    def guide(self):
        from pathlib import Path
        from disco.core.config import data_file
        guide = Path(data_file("guide", "Disco-Guide.pdf"))
        if not guide.exists():
            guide = Path(__file__).resolve().parents[3] / "docs" / "Disco-Guide.pdf"
        open_url(str(guide))
