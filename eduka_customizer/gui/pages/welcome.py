"""Welcome Screen page: design the four pages a user sees after logging in."""

import copy
import tempfile

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.gui import QPixmap
from eduka_customizer.qt.widgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                                          QPlainTextEdit, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from eduka_customizer.core import welcome
from eduka_customizer.gui.pages.appearance import IMAGES, ColorButton
from eduka_customizer.gui.widgets import FilePicker, Page, button, combo, hbox, label

BUTTONS = 3


class PageEditor(QWidget):
    """Editor of one welcome page."""

    def __init__(self, changed):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 10, 4, 4)
        self.enabled = QCheckBox("Show this page")
        lay.addWidget(self.enabled)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Title of the page")
        lay.addWidget(self.title)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Text. **bold**, *italic*, [link](https://example.org); an empty line "
                                     "starts a new paragraph.")
        self.text.setMinimumHeight(120)
        lay.addWidget(self.text)
        self.image = FilePicker("Picture of the page", IMAGES)
        self.position = combo(welcome.POSITIONS)
        self.align = combo([("center", "Centered"), ("left", "Left aligned")])
        self.show_logo = QCheckBox("Show the logo")
        self.background = QLineEdit()
        self.background.setPlaceholderText("#ffffff (empty: the screen's color)")
        self.background.setMaximumWidth(220)
        lay.addWidget(hbox(label("Picture:"), self.image))
        lay.addWidget(hbox(label("Picture position:"), self.position, label("Text:"), self.align, self.show_logo,
                           label("Background:"), self.background, None))
        lay.addWidget(label("Buttons (empty label = no button)", "cardTitle"))
        self.buttons = []
        for _ in range(BUTTONS):
            name = QLineEdit()
            name.setPlaceholderText("Label, e.g. Website")
            action = combo(welcome.ACTIONS)
            target = QLineEdit()
            target.setPlaceholderText("https://... or a program, e.g. firefox-esr")
            lay.addWidget(hbox(name, action, target))
            self.buttons.append((name, action, target))
        for w in (self.title, self.background):
            w.textChanged.connect(changed)
        self.text.textChanged.connect(changed)
        self.image.changed.connect(changed)
        for w in (self.position, self.align):
            w.currentIndexChanged.connect(changed)
        for w in (self.enabled, self.show_logo):
            w.toggled.connect(changed)
        for name, action, target in self.buttons:
            name.textChanged.connect(changed)
            target.textChanged.connect(changed)
            action.currentIndexChanged.connect(changed)

    def set(self, p):
        self.enabled.setChecked(p.get("enabled", True))
        self.title.setText(p.get("title", ""))
        self.text.setPlainText(p.get("text", ""))
        self.image.setText(p.get("image", ""))
        self.position.setCurrentIndex(max(0, self.position.findData(p.get("image_position", "right"))))
        self.align.setCurrentIndex(max(0, self.align.findData(p.get("align", "center"))))
        self.show_logo.setChecked(p.get("show_logo", True))
        self.background.setText(p.get("background", ""))
        buttons = p.get("buttons", [])
        for i, (name, action, target) in enumerate(self.buttons):
            b = buttons[i] if i < len(buttons) else {}
            name.setText(b.get("label", ""))
            action.setCurrentIndex(max(0, action.findData(b.get("action", "url"))))
            target.setText(b.get("target", ""))

    def get(self):
        return {"enabled": self.enabled.isChecked(), "title": self.title.text().strip(),
                "text": self.text.toPlainText().strip(), "image": self.image.text().strip(),
                "image_position": self.position.currentData(), "align": self.align.currentData(),
                "show_logo": self.show_logo.isChecked(), "background": self.background.text().strip(),
                "buttons": [{"label": n.text().strip(), "action": a.currentData(), "target": t.text().strip()}
                            for n, a, t in self.buttons if n.text().strip()]}


class Preview(QFrame):
    """A drawing of the welcome page, close to what the GTK program shows."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(380)
        self.setObjectName("welcomePreview")
        self.lay = QVBoxLayout(self)

    def show_page(self, d, n):
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        colors = d.get("colors", {})
        p = d["pages"][n]
        bg = p.get("background") or colors.get("background", "#ffffff")
        self.setStyleSheet("QFrame#welcomePreview {{ background: {}; border: 1px solid #c8d6d1; border-radius: 12px; }}"
                           "QFrame#welcomePreview QLabel {{ color: {}; background: transparent; }}"
                           .format(bg, colors.get("text", "#1d2b28")))
        center = p.get("align", "center") == "center"
        al = Qt.AlignmentFlag.AlignHCenter if center else Qt.AlignmentFlag.AlignLeft
        if p.get("show_logo", True) and d.get("logo"):
            pix = QPixmap(d["logo"])
            if not pix.isNull():
                logo = QLabel()
                logo.setPixmap(pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
                logo.setAlignment(al)
                self.lay.addWidget(logo)
        title = QLabel(welcome.to_markup(p.get("title", "")))
        title.setStyleSheet("font-size: 20pt; font-weight: bold; color: {};".format(colors.get("title", "#00a879")))
        title.setAlignment(al)
        title.setWordWrap(True)
        self.lay.addWidget(title)
        body = QHBoxLayout()
        text = QLabel(welcome.to_markup(p.get("text", "")).replace("\n", "<br>"))
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setAlignment(al | Qt.AlignmentFlag.AlignTop)
        img = None
        if p.get("image"):
            pix = QPixmap(p["image"])
            if not pix.isNull():
                img = QLabel()
                img.setPixmap(pix.scaled(260, 170, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        pos = p.get("image_position", "right")
        if img and pos == "top":
            img.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.lay.addWidget(img)
        if img and pos == "left":
            body.addWidget(img)
        body.addWidget(text, 1)
        if img and pos == "right":
            body.addWidget(img)
        self.lay.addLayout(body, 1)
        if img and pos == "bottom":
            img.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.lay.addWidget(img)
        row = QHBoxLayout()
        if center:
            row.addStretch(1)
        for b in p.get("buttons", []):
            btn = QLabel(b["label"])
            btn.setStyleSheet("background: {}; color: {}; border-radius: 8px; padding: 8px 18px; font-weight: bold;"
                              .format(colors.get("accent", "#00a879"), colors.get("button_text", "#ffffff")))
            row.addWidget(btn)
        row.addStretch(1)
        self.lay.addLayout(row)
        dots = " ".join("●" if i == n else "○" for i, pg in enumerate(d["pages"]) if pg.get("enabled", True))
        foot = QLabel("☑ {}        {}        {} · {} · {}".format(
            d.get("startup_label", ""), dots, d.get("back_label", "Back"), d.get("next_label", "Next"),
            d.get("close_label", "Close")))
        foot.setStyleSheet("color: #6b7d78; border-top: 1px solid #dde6e2; padding-top: 6px;")
        foot.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.lay.addWidget(foot)


class WelcomePage(Page):
    title = "Welcome Screen"
    nav_title = "Welcome Screen"
    subtitle = ("Four pages every user sees after logging in: your logo, titles, text, pictures and buttons that "
                "open a website, start a program or the installer. Users can untick 'Show this at startup'.")
    icon_names = ("system-help", "help-about")

    def build(self):
        self._loading = False
        c = self.card("Welcome screen")
        f = c.form()
        self.enabled = QCheckBox("Add the welcome screen to the image")
        f.addRow("", self.enabled)
        self.win_title = QLineEdit()
        f.addRow("Window title:", self.win_title)
        self.logo = FilePicker("Logo", IMAGES)
        f.addRow("Logo:", self.logo)
        self.show_when = combo(welcome.SHOW)
        f.addRow("Show:", self.show_when)
        self.width_ = QSpinBox()
        self.width_.setRange(300, 3000)
        self.height_ = QSpinBox()
        self.height_.setRange(300, 3000)
        f.addRow("Window size:", hbox(self.width_, label("×"), self.height_, None))
        self.colors = {k: ColorButton(v) for k, v in (("background", "#ffffff"), ("text", "#1d2b28"),
                                                      ("title", "#00a879"), ("accent", "#00a879"),
                                                      ("button_text", "#ffffff"))}
        f.addRow("Colors:", hbox(label("Background"), self.colors["background"], label("Text"), self.colors["text"],
                                 label("Titles"), self.colors["title"], None))
        f.addRow("", hbox(label("Buttons"), self.colors["accent"], label("Button text"), self.colors["button_text"],
                          None))
        self.labels = {k: QLineEdit() for k in ("startup_label", "back_label", "next_label", "close_label")}
        for k, w in self.labels.items():
            w.setPlaceholderText({"startup_label": "Show this at startup", "back_label": "Back",
                                  "next_label": "Next", "close_label": "Close"}[k])
        f.addRow("Texts:", hbox(self.labels["startup_label"], self.labels["back_label"]))
        f.addRow("", hbox(self.labels["next_label"], self.labels["close_label"]))

        c = self.card("Pages", "Design each page; the preview shows the page you are editing.")
        self.tabs = QTabWidget()
        self.editors = []
        for i in range(welcome.PAGES):
            ed = PageEditor(self._changed)
            self.editors.append(ed)
            self.tabs.addTab(ed, "Page {}".format(i + 1))
        self.tabs.currentChanged.connect(lambda _i: self._changed())
        c.add(self.tabs)

        c = self.card("Preview")
        self.preview = Preview()
        c.add(self.preview)
        self.state_label = label("", "muted")
        c.add(self.state_label)
        c.add(hbox(button("Remove from the image", self.remove, "danger"), button("Reset to the example", self.reset),
                   None, button("Open the real welcome screen", self.open_real,
                                tooltip="Runs the GTK program on this computer (needs python3-gi)"),
                   button("Save design", self.save), button("Apply to the image", self.apply, "primary")))
        for w in [self.win_title] + list(self.labels.values()):
            w.textChanged.connect(self._changed)
        self.logo.changed.connect(self._changed)
        for b in self.colors.values():
            b.clicked.connect(self._changed)

    # Data ---------------------------------------------------------------------------
    def design(self):
        d = welcome.design(self.project) if self.project else {}
        d.update({"enabled": self.enabled.isChecked(), "title": self.win_title.text().strip(),
                  "logo": self.logo.text().strip(), "show": self.show_when.currentData(),
                  "width": self.width_.value(), "height": self.height_.value(),
                  "colors": {k: b.color for k, b in self.colors.items()}})
        d.update({k: w.text().strip() for k, w in self.labels.items()})
        d["pages"] = [ed.get() for ed in self.editors]
        return d

    def load(self, d):
        self._loading = True
        self.enabled.setChecked(d.get("enabled", True))
        self.win_title.setText(d.get("title", ""))
        self.logo.setText(d.get("logo", ""))
        self.show_when.setCurrentIndex(max(0, self.show_when.findData(d.get("show", "startup"))))
        self.width_.setValue(int(d.get("width", 860)))
        self.height_.setValue(int(d.get("height", 560)))
        for k, b in self.colors.items():
            b.set(d.get("colors", {}).get(k, b.color))
        for k, w in self.labels.items():
            w.setText(d.get(k, ""))
        for ed, p in zip(self.editors, d["pages"]):
            ed.set(p)
        self._loading = False
        self._changed()

    def refresh(self):
        if self.project:
            if not self.logo.text() or getattr(self, "_for", None) != self.project.path:
                self._for = self.project.path
                d = welcome.design(self.project)
                if not d.get("logo"):
                    logo = (self.project.state.get("branding", {}).get("spec") or {}).get("logo", "")
                    d["logo"] = logo
                self.load(d)
            ok = welcome.Welcome(self.project).installed()
            self.state_label.setText("Installed in the image." if ok else "Not in the image yet.")

    def _changed(self, *_a):
        if self._loading or not self.project:
            return
        d = self.design()
        self.preview.show_page(d, self.tabs.currentIndex())

    # Actions -------------------------------------------------------------------------
    def _checked(self):
        d = self.design()
        problems = welcome.validate(d)
        if problems:
            QMessageBox.warning(self, "Welcome Screen", "\n".join(problems))
            return None
        return d

    def save(self):
        d = self._checked()
        if d:
            welcome.Welcome(self.project).save(d)
            self.main.stage_label.setText("Welcome screen design saved")

    def apply(self):
        d = self._checked()
        if not d:
            return
        proj = self.project
        if not d.get("enabled"):
            self.task("Remove the welcome screen", lambda t: (welcome.Welcome(proj).save(d),
                                                              welcome.Welcome(proj).remove()), lambda _r: self.refresh())
            return
        self.task("Welcome screen", lambda t: welcome.Welcome(proj).apply(copy.deepcopy(d)),
                  lambda _r: self.refresh())

    def remove(self):
        proj = self.project
        self.task("Remove the welcome screen", lambda t: welcome.Welcome(proj).remove(), lambda _r: self.refresh())

    def reset(self):
        if QMessageBox.question(self, "Welcome Screen", "Replace your design with the example?") == \
                QMessageBox.StandardButton.Yes:
            self.load(welcome.default_design(self.project))

    def open_real(self):
        d = self._checked()
        if not d:
            return
        try:
            proc = welcome.Welcome(self.project).preview(d, tempfile.mkdtemp(prefix="eduka-welcome-"))
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Welcome Screen", str(e))
            return
        try:
            proc.wait(timeout=1.5)
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            QMessageBox.information(self, "Welcome Screen", "The welcome screen could not open on this computer "
                                    "(it needs python3-gi and gir1.2-gtk-3.0).\n\n" + err[-600:])
        except Exception:
            pass  # still running: it is open
