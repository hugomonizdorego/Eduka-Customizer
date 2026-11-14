"""Start: extract an ISO into a new project, or continue a project you started before."""

import json
import os
import re
from pathlib import Path

import threading

from disco.qt.core import QObject, Qt, pyqtSignal
from disco.qt.widgets import (QCheckBox, QFileDialog, QInputDialog, QLineEdit, QListWidget, QListWidgetItem,
                              QMessageBox, QTabWidget, QVBoxLayout, QWidget)

from disco.core.config import settings
from disco.core.log import log
from disco.gui.pages.language import combo_locale, language_combo
from disco.gui.widgets import FilePicker, Page, button, combo, hbox, label


def apply_language(proj, choice):
    """Set the chosen default language on a freshly created root filesystem."""
    if not choice:
        return
    from disco.core.language import Language
    locale, packs = choice
    try:
        Language(proj).apply(locale, packs=packs)
    except Exception as e:  # the new system is usable without it
        log.warning("Could not set the language %s: %s (set it on the Language page)", locale, e)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "my-distro"


class NetCheck(QObject):
    """Checks the internet connection in the background, without freezing the window. A plain
    daemon thread: closing D!sco while it checks is fine (a QThread would abort the program)."""
    result = pyqtSignal(bool)

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def isRunning(self):
        return getattr(self, "running", False)

    def _run(self):
        from disco.core import net
        try:
            ok = net.online()
        except Exception:  # never take the window down for a check
            ok = False
        self.running = False
        try:
            self.result.emit(ok)
        except RuntimeError:  # the window is already closed
            pass


def project_summary(path):
    """(name, 'Step N of M · last change') of a project folder, read without opening it."""
    try:
        st = json.loads(Path(path, "project.json").read_text())
    except (OSError, ValueError):
        return Path(path).name, ""
    name = (st.get("identity") or {}).get("name") or st.get("name") or Path(path).name
    hist = st.get("history") or []
    when = hist[-1].get("time", "").replace("T", " ")[:16] if hist else ""
    done = st.get("steps_done") or []
    built = st.get("last_iso") or st.get("last_image")
    state = "finished: {}".format(Path(built).name) if built else (
        "all steps done" if "*" in done else "{} step(s) done".format(len(done) + (1 if Path(path, "rootfs/usr").is_dir() else 0)))
    return name, "{}{}".format(state, " · last change " + when if when else "")


class ProjectPage(Page):
    title = "Start"
    nav_title = "Start"
    subtitle = ("Choose where your distribution starts: extract a live ISO into a new project, or continue a project "
                "you started before. Everything of a project is kept in its own folder.")
    icon_names = ("go-home", "user-home")
    needs_rootfs = False

    def build(self):
        net = self.card()
        self.net_label = label("Checking the internet connection...", wrap=True)
        net.add(hbox(self.net_label, None, button("Check again", self.check_net)))

        a, b = self.row(self.card("Customize an ISO", "A Debian or Debian-based live ISO (Debian, Devuan, LMDE, "
                                                      "MX Linux...). Recommended: the small Debian live "
                                                      "standard ISO."),
                        self.card("Continue a project", "Open a project you started before and go on where you "
                                                        "stopped."))
        f = a.form()
        self.iso = FilePicker("Choose ISO image", "ISO images (*.iso)")
        self.iso.changed.connect(self._iso_chosen)
        f.addRow("ISO file:", self.iso)
        self.name = QLineEdit()
        self.name.setPlaceholderText("My Linux")
        self.name.textEdited.connect(self._name_edited)
        f.addRow("Name:", self.name)
        self.folder = FilePicker("Project folder", directory=True)
        self.folder.setText(os.path.join(settings().get("general", "projects_dir"), "my-linux"))
        f.addRow("Folder:", self.folder)
        self.lang = language_combo()
        self.lang.insertItem(0, "Keep the language of the ISO", "")
        self.lang.setCurrentIndex(0)
        from disco.qt.widgets import QComboBox, QSizePolicy
        self.lang.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.lang.setMinimumContentsLength(18)
        self.lang.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lang_packs = QCheckBox("Install translations (needs internet)")
        f.addRow("Language:", self.lang)
        f.addRow("", self.lang_packs)
        a.add(hbox(None, button("Extract and start  ▶", self.extract, "primary", ("media-optical",))))

        self.recent = QListWidget()
        self.recent.setMinimumHeight(170)
        self.recent.setWordWrap(True)
        self.recent.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.recent.itemDoubleClicked.connect(lambda _it: self.continue_selected())
        b.add(self.recent)
        b.add(hbox(button("Open another folder...", self.browse, icon_names=("document-open",)), None,
                   button("Continue  ▶", self.continue_selected, "primary")))

        self.more = self.card("Other ways to start", "For a new system without an ISO, an official Debian ISO "
                                                     "downloaded for you, or a copy of this computer.")
        tabs = QTabWidget()
        self.more.add(tabs)
        # Download ----------------------------------------------------------------------------------
        t = QWidget()
        v = QVBoxLayout(t)
        v.addWidget(label("Download an official Debian live ISO (checked with Debian's SHA256SUMS) into the project "
                          "and extract it. Needs internet.", "muted"))
        self.dl_suite = combo([("stable", "Debian stable"), ("testing", "Debian testing (weekly)")])
        self.dl_image = combo([])
        v.addWidget(hbox(self.dl_suite, button("Show the images", self.refresh_images), self.dl_image))
        v.addWidget(hbox(None, button("Download and extract  ▶", self.download, "primary", ("download", "go-down"))))
        tabs.addTab(t, "Download Debian")
        # New base -----------------------------------------------------------------------------------
        t = QWidget()
        v = QVBoxLayout(t)
        v.addWidget(label("A new minimal Debian or Devuan system made with mmdebstrap, for a PC, an ARM64 machine, a "
                          "Raspberry Pi or RISC-V (other processors run through qemu-user). Add the desktop in "
                          "step 3. Needs internet.", "muted"))
        from disco.core import platforms
        self.bs_family = combo([("debian", "Debian"), ("devuan", "Devuan (without systemd)")])
        self.bs_suite = combo([("stable", "Stable"), ("testing", "Testing"), ("sid", "Unstable (sid / ceres)"),
                               ("oldstable", "Oldstable")])
        self.bs_arch = combo([(p.id, "{} ({})".format(p.name, p.arch)) for p in platforms.PLATFORMS])
        self.bs_variant = combo([("important", "Important (recommended)"), ("standard", "Standard"),
                                 ("minbase", "Minimal")])
        v.addWidget(hbox(self.bs_family, self.bs_suite, self.bs_arch, self.bs_variant))
        v.addWidget(hbox(None, button("Make the new system  ▶", self.bootstrap, "primary", ("system-run",))))
        tabs.addTab(t, "New system (no ISO)")
        # Snapshot -----------------------------------------------------------------------------------
        t = QWidget()
        v = QVBoxLayout(t)
        v.addWidget(label("Copy the running Debian-based system. 'Distribution' leaves out personal accounts, "
                          "/home and /root; 'Backup' keeps them - never share a backup ISO.", "muted"))
        self.snap_mode = combo([("dist", "Distribution (no personal data)"),
                                ("backup", "Backup (keeps /home and users)")])
        v.addWidget(hbox(self.snap_mode, None, button("Copy this computer  ▶", self.snapshot, "primary")))
        tabs.addTab(t, "This computer")

        self.status = self.card("This project")
        self.purpose = label("", "muted")
        self.status.add(hbox(self.purpose, None, button("What is it for? Recommendations...", self.choose_purpose)))
        self.status_text = label("", wrap=True)
        self.status.add(self.status_text)
        self.history = QListWidget()
        self.history.setMaximumHeight(150)
        self.status.add(self.history)
        self._net = None
        self._name_auto = True

    # Internet --------------------------------------------------------------------------------------------
    def check_net(self):
        if self._net is not None and self._net.isRunning():
            return
        self.net_label.setText("Checking the internet connection...")
        self._net = NetCheck(self)
        self._net.result.connect(self._net_result)
        self._net.start()

    def _net_result(self, ok):
        from disco.core import net
        self.main.online = ok
        if ok:
            self.net_label.setText("<b>✔ Internet connection:</b> packages, desktops, Flatpaks and kernels can be "
                                   "installed.")
        else:
            self.net_label.setText("<b>⚠ " + net.NO_INTERNET + "</b>")

    # Helpers --------------------------------------------------------------------------------------------------
    def _iso_chosen(self, path):
        if path and self._name_auto and not self.name.text().strip():
            stem = Path(path).stem
            nice = "My Linux" if stem.startswith("debian-live") else stem.replace("-", " ").replace("_", " ")[:40]
            self.name.setText(nice)
            self._name_edited(nice)

    def _name_edited(self, text):
        base = settings().get("general", "projects_dir")
        cur = self.folder.text()
        if not cur or Path(cur).parent == Path(base):
            self.folder.setText(os.path.join(base, slug(text)))

    def refresh(self):
        self.recent.clear()
        for p in settings().recent_projects():
            name, state = project_summary(p)
            it = QListWidgetItem("{}  —  {}\n{}".format(name, p, state))
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.recent.addItem(it)
        if not self.recent.count():
            it = QListWidgetItem("No projects yet: extract an ISO on the left.")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recent.addItem(it)
        else:
            self.recent.setCurrentRow(0)
        if self._net is None:
            self.check_net()
        has = self.project is not None
        self.status.setVisible(has)
        if not has:
            return
        p = self.project
        d = p.distro
        src = p.state.get("source", {})
        lines = ["<b>Folder:</b> {}".format(p.path),
                 "<b>Started from:</b> {} {}".format(src.get("kind") or "nothing yet", src.get("path") or ""),
                 "<b>System:</b> {}".format(d.summary() if d.id else "none yet: extract an ISO"),
                 "<b>Last image:</b> {}".format(p.state.get("last_iso") or p.state.get("last_image") or
                                                "not built yet")]
        self.status_text.setText("<br>".join(lines))
        from disco.core import profiles
        pid = p.state.get("purpose")
        try:
            self.purpose.setText("Purpose: <b>{}</b>".format(profiles.get(pid)["name"]) if pid else
                                 "Purpose: not chosen yet")
        except KeyError:
            self.purpose.setText("Purpose: " + pid)
        self.history.clear()
        for h in reversed(p.state.get("history", [])[-30:]):
            self.history.addItem("{}  {}  {}".format(h["time"].replace("T", " "), h["action"], h["detail"]))

    def choose_purpose(self):
        from disco.gui.purpose import ask_purpose
        if not self.project or not self.project.has_rootfs():
            QMessageBox.information(self, "Purpose", "Extract an ISO first.")
            return
        ask_purpose(self, force=True)

    def project_changed(self):
        self.refresh()

    # Projects ---------------------------------------------------------------------------------------------------
    def _target_project(self):
        """Open (or create) the project of the folder field. False when that did not work."""
        folder = os.path.realpath(self.folder.text().strip() or ".")
        name = self.name.text().strip() or Path(folder).name
        if self.project and str(self.project.path) == folder:
            return True
        if Path(folder, "project.json").exists():
            return self.main.open_project(folder)
        if Path(folder).exists() and any(Path(folder).iterdir()):
            if QMessageBox.question(self, "Project folder", "{} is not empty and is not a D!sco project. Use it "
                                    "anyway?".format(folder)) != QMessageBox.StandardButton.Yes:
                return False
        if not self.main.open_project(folder, create=True, name=name):
            return False
        self.project.state["name"] = name
        self.project.save()
        return True

    def continue_selected(self):
        it = self.recent.currentItem()
        path = it.data(Qt.ItemDataRole.UserRole) if it else None
        if path and self.main.open_project(path):
            self.main.continue_project()

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Open project folder", settings().get("general", "projects_dir"))
        if d:
            if not Path(d, "project.json").exists():
                QMessageBox.information(self, "Open project", "{} is not a D!sco project (it has no project.json)."
                                        .format(d))
                return
            if self.main.open_project(d):
                self.main.continue_project()

    def _confirm_replace(self):
        if self.project.has_rootfs():
            r = QMessageBox.question(self, "Replace the system",
                                     "This project already has a system. Replace it? Everything changed in it is "
                                     "lost.")
            return r == QMessageBox.StandardButton.Yes
        return True

    def _language(self):
        if not self.lang.currentData() and self.lang.currentIndex() == 0:
            return None
        return combo_locale(self.lang), self.lang_packs.isChecked()

    def _done(self, info):
        from disco.core import permissions
        # A new system: its steps start again (Continue must not jump to Build of the old one).
        self.project.state["steps_done"] = []
        self.project.save()
        permissions.share_user_folders(self.project)
        self.main.update_state()
        self.refresh()
        self.main.stage_label.setText("Ready: {}. Next: step 2.".format(info.summary()))
        QMessageBox.information(self, "Ready", "The system is ready to customize:\n{}\n\nPress Next at the bottom "
                                "of each step; skip what you do not want to change.".format(info.summary()))
        from disco.gui.purpose import ask_purpose
        ask_purpose(self)
        self.main.continue_project()

    def extract(self):
        iso_path = self.iso.text()
        if not iso_path or not Path(iso_path).is_file():
            QMessageBox.information(self, "Customize an ISO", "Choose the ISO file first.")
            return
        if not self._target_project() or not self._confirm_replace():
            return
        from disco.core import iso
        proj, lang = self.project, self._language()

        def work(t):
            info = iso.extract(proj, iso_path, t.set_progress)
            apply_language(proj, lang)
            return info
        self.task("Extract ISO", work, self._done, queue=False)

    def refresh_images(self):
        from disco.core import download
        suite = self.dl_suite.currentData()

        def done(images):
            self.dl_image.clear()
            for name, _sha in images:
                self.dl_image.addItem(name, name)
            standard = self.dl_image.findText("standard", Qt.MatchFlag.MatchContains)
            if standard >= 0:
                self.dl_image.setCurrentIndex(standard)
                self.dl_image.setItemText(standard, self.dl_image.itemText(standard) + "  (recommended)")
        self.task("List Debian images", lambda t: download.list_images(suite), done, queue=False)

    def download(self):
        from disco.core import download, iso
        name = self.dl_image.currentData()
        if not name:
            QMessageBox.information(self, "Download", "Press 'Show the images' and choose one first.")
            return
        if not self._target_project() or not self._confirm_replace():
            return
        suite = self.dl_suite.currentData()
        proj, lang = self.project, self._language()

        def work(t):
            t.set_stage("Downloading " + name)
            path = download.download(suite, name, proj.path / "downloads", t.set_progress)
            t.set_stage("Extracting")
            info = iso.extract(proj, path, t.set_progress)
            apply_language(proj, lang)
            return info
        self.task("Download Debian live image", work, self._done, queue=False)

    def bootstrap(self):
        if not self._target_project() or not self._confirm_replace():
            return
        from disco.core import bootstrap
        proj, lang = self.project, self._language()
        suite, plat, variant = self.bs_suite.currentData(), self.bs_arch.currentData(), self.bs_variant.currentData()
        devuan = self.bs_family.currentData() == "devuan"

        def work(t):
            info = bootstrap.bootstrap(proj, suite, None, variant, devuan=devuan, platform_id=plat)
            apply_language(proj, lang)
            return info
        self.task("New {} {} system".format("Devuan" if devuan else "Debian", suite), work, self._done, queue=False)

    def snapshot(self):
        if not self._target_project() or not self._confirm_replace():
            return
        mode = self.snap_mode.currentData()
        if mode == "backup":
            text, ok = QInputDialog.getText(self, "Backup copy",
                                            "A backup ISO contains your personal files and passwords.\n"
                                            "Type BACKUP to continue:")
            if not ok or text != "BACKUP":
                return
        from disco.core import snapshot
        proj = self.project
        self.task("Copy this computer", lambda t: snapshot.snapshot(proj, mode), self._done, queue=False)
