"""Start page: create/open projects and choose the source of the image."""

import os
from pathlib import Path

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QFileDialog, QInputDialog, QLineEdit, QListWidget,
                                          QMessageBox, QTabWidget, QVBoxLayout, QWidget)

from eduka_customizer.core.config import settings
from eduka_customizer.core.log import log
from eduka_customizer.gui.pages.language import combo_locale, language_combo
from eduka_customizer.gui.widgets import FilePicker, Page, button, combo, hbox, label


def apply_language(proj, choice):
    """Set the chosen default language on a freshly created root filesystem."""
    if not choice:
        return
    from eduka_customizer.core.language import Language
    locale, packs = choice
    try:
        Language(proj).apply(locale, packs=packs)
    except Exception as e:  # the new system is usable without it
        log.warning("Could not set the language %s: %s (set it on the Language page)", locale, e)


class ProjectPage(Page):
    title = "Start"
    nav_title = "Start / Project"
    subtitle = ("Build your own Debian-based distribution from a Debian live ISO (the minimal 'standard' "
                "ISO is recommended), a Debian-derivative ISO such as LMDE, a fresh Debian base or this computer.")
    icon_names = ("go-home", "user-home")
    needs_rootfs = False

    def build(self):
        a, b = self.row(self.card("New project", "Every project keeps its own root filesystem, "
                                                 "ISO tree, cache and build output."),
                        self.card("Open project", "Continue working on an earlier project."))
        f = a.form()
        self.name = QLineEdit()
        self.name.setPlaceholderText("project name, e.g. My Linux")
        f.addRow("Name:", self.name)
        self.folder = FilePicker("Project folder", directory=True)
        base = settings().get("general", "projects_dir")
        self.folder.setText(os.path.join(base, "my-distro"))
        f.addRow("Folder:", self.folder)
        a.add(hbox(None, button("Create project", self.create, "primary", ("folder-new",))))

        self.recent = QListWidget()
        self.recent.setMinimumHeight(110)
        self.recent.itemDoubleClicked.connect(lambda it: self.main.open_project(it.text()))
        b.add(self.recent)
        b.add(hbox(None, button("Open selected", self.open_selected),
                   button("Browse...", self.browse, icon_names=("document-open",))))

        self.source = self.card("Source of the image",
                                "Choose where the root filesystem comes from. Replacing the source "
                                "deletes the current root filesystem of this project.")
        self.lang = language_combo()
        self.lang.insertItem(0, "Keep the language of the source", "")
        self.lang.setCurrentIndex(0)
        self.lang_packs = QCheckBox("Install translations (needs internet)")
        self.source.add(hbox(label("Default language:"), self.lang, self.lang_packs))
        tabs = QTabWidget()
        self.source.add(tabs)

        # ISO ------------------------------------------------------------------
        t = QWidget()
        v = QVBoxLayout(t)
        v.addWidget(label("<b>Recommended: the Debian live <i>standard</i> ISO</b> "
                          "(debian-live-*-amd64-standard.iso): it has no desktop, so you start from a small, "
                          "clean system and add only what you choose. Every Debian-based live ISO works too: "
                          "the other Debian live ISOs and Debian derivatives such as Linux Mint "
                          "Debian Edition (LMDE). Ubuntu-based images (Ubuntu, Linux Mint) are refused.",
                          "muted"))
        self.iso = FilePicker("Choose ISO image", "ISO images (*.iso)")
        v.addWidget(self.iso)
        v.addWidget(hbox(None, button("Extract ISO", self.extract, "primary", ("media-optical",))))
        tabs.addTab(t, "Debian / Debian-based ISO")

        # Download ----------------------------------------------------------------
        t = QWidget()
        v = QVBoxLayout(t)
        v.addWidget(label("Download an official Debian live image (verified with SHA256SUMS). "
                          "Debian has no live images for sid: start from testing, then switch "
                          "the repositories to sid.", "muted"))
        self.dl_suite = combo([("stable", "Debian stable"), ("testing", "Debian testing (weekly)")])
        self.dl_image = combo([])
        v.addWidget(hbox(self.dl_suite, button("Refresh list", self.refresh_images), self.dl_image))
        v.addWidget(hbox(None, button("Download and extract", self.download, "primary",
                                      ("download", "go-down"))))
        tabs.addTab(t, "Download Debian")

        # Bootstrap ----------------------------------------------------------------
        t = QWidget()
        v = QVBoxLayout(t)
        v.addWidget(label("Create a minimal Debian system with mmdebstrap and add your desktop "
                          "afterwards. The boot menu is generated (BIOS + UEFI, Secure Boot when "
                          "shim-signed is installed).", "muted"))
        self.bs_suite = combo([("stable", "Debian stable"), ("testing", "Debian testing"),
                               ("sid", "Debian sid (unstable)")])
        self.bs_arch = combo(["amd64", "i386", "arm64"])
        self.bs_variant = combo([("important", "Important (recommended)"), ("standard", "Standard"),
                                 ("minbase", "Minimal")])
        v.addWidget(hbox(self.bs_suite, self.bs_arch, self.bs_variant))
        v.addWidget(hbox(None, button("Bootstrap new base", self.bootstrap, "primary",
                                      ("system-run",))))
        tabs.addTab(t, "New Debian base")

        # Snapshot -------------------------------------------------------------------
        t = QWidget()
        v = QVBoxLayout(t)
        v.addWidget(label("Experimental (remastersys / penguins-eggs style): copy the running "
                          "Debian-based system. 'Distribution' removes personal "
                          "accounts and /home; 'Backup' keeps them - never share a backup ISO.",
                          "muted"))
        self.snap_mode = combo([("dist", "Distribution (no personal data)"),
                                ("backup", "Backup (keeps /home and users)")])
        v.addWidget(hbox(self.snap_mode, None, button("Snapshot this computer", self.snapshot,
                                                      "primary")))
        tabs.addTab(t, "This computer")

        self.status = self.card("Project status")
        self.purpose = label("", "muted")
        self.status.add(hbox(self.purpose, None, button("What is it for? Recommendations...", self.choose_purpose)))
        self.status_text = label("", wrap=True)
        self.status.add(self.status_text)
        self.history = QListWidget()
        self.history.setMaximumHeight(160)
        self.status.add(self.history)

    # Helpers -----------------------------------------------------------------
    def refresh(self):
        self.recent.clear()
        for p in settings().recent_projects():
            self.recent.addItem(p)
        has = self.project is not None
        self.source.setEnabled(has)
        self.status.setVisible(has)
        if not has:
            return
        p = self.project
        d = p.distro
        src = p.state.get("source", {})
        lines = ["<b>Folder:</b> {}".format(p.path),
                 "<b>Source:</b> {} {}".format(src.get("kind") or "none yet", src.get("path") or ""),
                 "<b>System:</b> {}".format(d.summary() if d.id else "no root filesystem yet"),
                 "<b>Boot mode:</b> {}".format({"replay": "reuse boot setup of the source ISO",
                                                "generate": "generated by Eduka-Customizer"}.get(
                                                   src.get("boot_mode"), "-")),
                 "<b>Last ISO:</b> {}".format(p.state.get("last_iso") or "not built yet")]
        self.status_text.setText("<br>".join(lines))
        from eduka_customizer.core import profiles
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
        from eduka_customizer.gui.purpose import ask_purpose
        if not self.project.has_rootfs():
            QMessageBox.information(self, "Purpose", "Extract an ISO or create a Debian base first.")
            return
        ask_purpose(self, force=True)

    def project_changed(self):
        self.refresh()

    def create(self):
        folder = self.folder.text()
        if not folder:
            return
        if Path(folder, "project.json").exists():
            self.main.open_project(folder)
        elif self.main.open_project(folder, create=True, name=self.name.text().strip() or Path(folder).name):
            self.project.state["name"] = self.name.text().strip() or Path(folder).name
            self.project.save()
        self.refresh()

    def open_selected(self):
        it = self.recent.currentItem()
        if it:
            self.main.open_project(it.text())
            self.refresh()

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Open project folder",
                                             settings().get("general", "projects_dir"))
        if d:
            self.main.open_project(d)
            self.refresh()

    def _confirm_replace(self):
        if self.project.has_rootfs():
            r = QMessageBox.question(self, "Replace root filesystem",
                                     "This project already has a root filesystem. Replace it? "
                                     "All customizations in it will be lost.")
            return r == QMessageBox.StandardButton.Yes
        return True

    def _language(self):
        if not self.lang.currentData() and self.lang.currentIndex() == 0:
            return None
        return combo_locale(self.lang), self.lang_packs.isChecked()

    def _done(self, info):
        self.main.update_state()
        self.refresh()
        QMessageBox.information(self, "Ready", "The image is ready to customize:\n{}".format(info.summary()))
        from eduka_customizer.gui.purpose import ask_purpose
        ask_purpose(self)

    def extract(self):
        iso_path = self.iso.text()
        if not iso_path or not self._confirm_replace():
            return
        from eduka_customizer.core import iso
        proj, lang = self.project, self._language()

        def work(t):
            info = iso.extract(proj, iso_path, t.set_progress)
            apply_language(proj, lang)
            return info
        self.task("Extract ISO", work, self._done)

    def refresh_images(self):
        from eduka_customizer.core import download
        suite = self.dl_suite.currentData()

        def done(images):
            self.dl_image.clear()
            for name, _sha in images:
                self.dl_image.addItem(name, name)
            # The standard image (no desktop) is the recommended start.
            standard = self.dl_image.findText("standard", Qt.MatchFlag.MatchContains)
            if standard >= 0:
                self.dl_image.setCurrentIndex(standard)
                self.dl_image.setItemText(standard, self.dl_image.itemText(standard) + "  (recommended)")
        self.task("List Debian images", lambda t: download.list_images(suite), done)

    def download(self):
        from eduka_customizer.core import download, iso
        name = self.dl_image.currentData()
        if not name:
            QMessageBox.information(self, "Download", "Refresh the list and choose an image first.")
            return
        if not self._confirm_replace():
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
        self.task("Download Debian live image", work, self._done)

    def bootstrap(self):
        if not self._confirm_replace():
            return
        from eduka_customizer.core import bootstrap
        proj, lang = self.project, self._language()
        suite, arch, variant = self.bs_suite.currentData(), self.bs_arch.currentData(), self.bs_variant.currentData()

        def work(t):
            info = bootstrap.bootstrap(proj, suite, arch, variant)
            apply_language(proj, lang)
            return info
        self.task("Bootstrap Debian " + suite, work, self._done)

    def snapshot(self):
        if not self._confirm_replace():
            return
        mode = self.snap_mode.currentData()
        if mode == "backup":
            text, ok = QInputDialog.getText(self, "Backup snapshot",
                                            "A backup ISO contains your personal files and passwords.\n"
                                            "Type BACKUP to continue:")
            if not ok or text != "BACKUP":
                return
        from eduka_customizer.core import snapshot
        proj = self.project
        self.task("Snapshot this computer", lambda t: snapshot.snapshot(proj, mode), self._done)
