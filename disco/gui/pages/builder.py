"""Builder: the whole distribution on one page, step by step or with one click.

Choose a preset (or fill in the fields), tick the package lists, then press the
step buttons in their order (Prepare, Build base, Packages, Overlay & scripts,
Make image) or simply "Build all". Everything else of D!sco (branding, boot,
installer...) refines what this page builds.
"""

import os
import subprocess
import sys
from pathlib import Path

from disco.qt.core import Qt
from disco.qt.widgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
                              QGridLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                              QListWidgetItem, QMessageBox, QPlainTextEdit, QSplitter, QTreeWidget,
                              QTreeWidgetItem, QVBoxLayout, QWidget)

from disco.core import pipeline, platforms, presets
from disco.core.config import settings
from disco.core.pkglists import Lists, catalog
from disco.gui.widgets import Card, FilePicker, Page, button, combo, hbox, label

SUITES = [("stable", "Stable"), ("testing", "Testing"), ("sid", "Unstable (sid)"), ("oldstable", "Oldstable")]
INITS = [("systemd", "systemd"), ("sysvinit", "SysVinit"), ("openrc", "OpenRC"), ("runit", "runit")]
INSTALLERS = [("calamares", "Calamares (installs the live system on a disk)"),
              ("none", "None: live system only"),
              ("debs", "My own .deb packages (debs folder)")]
METHODS = [("disco", "D!sco: debootstrap → chroot → squashfs → xorriso"),
           ("live-build", "Debian live-build (lb config, lb build)")]


class ListEditor(QDialog):
    """Edit one package list: tick programs in the catalog or type package names."""

    def __init__(self, parent, title, packages, comment=""):
        super().__init__(parent)
        self.setWindowTitle("Package list: " + title)
        self.resize(900, 600)
        lay = QVBoxLayout(self)
        self.title = QLineEdit(title)
        lay.addWidget(hbox(QLabel("Title:"), self.title))
        split = QSplitter()
        lay.addWidget(split, 1)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(label("One Debian package per line. '#' starts a comment, '-name' removes a package.",
                           "muted"))
        self.text = QPlainTextEdit("\n".join(packages) + ("\n" if packages else ""))
        lv.addWidget(self.text, 1)
        self.comment = QPlainTextEdit(comment)
        self.comment.setMaximumHeight(70)
        self.comment.setPlaceholderText("What this list is for (a comment at the top of the file)")
        lv.addWidget(self.comment)
        split.addWidget(left)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the catalog...")
        self.search.textChanged.connect(self._filter)
        rv.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Program", "Package", "What it is"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 150)
        have = set(self._names())
        for cat in catalog():
            top = QTreeWidgetItem([cat["name"], "", ""])
            top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.tree.addTopLevelItem(top)
            for pkg, name, desc in cat["apps"]:
                it = QTreeWidgetItem([name, pkg, desc])
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, Qt.CheckState.Checked if pkg in have else Qt.CheckState.Unchecked)
                top.addChild(it)
        self.tree.expandAll()
        self.tree.itemChanged.connect(self._ticked)
        rv.addWidget(label("Tick programs to add them to the list, untick to take them out.", "muted"))
        rv.addWidget(self.tree, 1)
        split.addWidget(right)
        split.setSizes([330, 570])
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _names(self):
        return [l.split("#")[0].strip() for l in self.text.toPlainText().splitlines() if l.split("#")[0].strip()]

    def _ticked(self, item, col):
        pkg = item.text(1)
        if col != 0 or not pkg:
            return
        names = self._names()
        if item.checkState(0) == Qt.CheckState.Checked and pkg not in names:
            names.append(pkg)
        elif item.checkState(0) != Qt.CheckState.Checked:
            names = [n for n in names if n != pkg]
        self.text.setPlainText("\n".join(names) + ("\n" if names else ""))

    def _filter(self, text):
        words = text.lower().split()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            shown = 0
            for j in range(top.childCount()):
                it = top.child(j)
                hay = " ".join(it.text(c) for c in range(3)).lower()
                hide = bool(words) and not all(w in hay for w in words)
                it.setHidden(hide)
                shown += not hide
            top.setHidden(shown == 0)

    def result_values(self):
        return self.title.text().strip(), self._names(), self.comment.toPlainText().strip()


class BuilderPage(Page):
    title = "Builder"
    nav_title = "Builder"
    subtitle = ("Your distribution on one page: choose a preset or fill in the fields, tick the package "
                "lists, then build step by step or press Build all. Debian and Devuan, for PCs, ARM64, "
                "Raspberry Pi and RISC-V.")
    icon_names = ("applications-engineering", "system-run", "go-home")
    needs_rootfs = False

    def build(self):
        # Preset bar ---------------------------------------------------------------------------
        bar = self.card("Preset", "A preset holds every choice of this page and the package lists. The presets "
                                  "of D!sco are a good start; save your own under a new name.")
        self.preset = combo([])
        self.preset.setMinimumWidth(320)
        bar.add(hbox(self.preset, button("Load", self.load_preset, "primary", ("document-open",)),
                     button("Save", self.save_preset, icon_names=("document-save",)),
                     button("File...", self.preset_file, icon_names=("document-import", "folder")),
                     button("Delete", self.delete_preset, "danger", ("edit-delete",)),
                     button("New", self.new_preset, icon_names=("document-new",)), None))

        # Distribution ----------------------------------------------------------------------------
        dist, steps = self.row(Card("Distribution"), Card("Build", "Press the steps in order, or Build all. "
                                                                   "A step can be run again at any time."))
        f = dist.form()
        self.name = QLineEdit()
        self.name.setPlaceholderText("My Linux")
        f.addRow("Distro name:", self.name)
        self.folder = FilePicker("Build folder", directory=True)
        self.folder.setText(os.path.join(settings().get("general", "projects_dir"), "my-distro"))
        f.addRow("Build path:", self.folder)
        self.platform = combo([(p.id, "{} — {}{}".format(p.name, p.arch, " (experimental)" if p.experimental
                                                                         else "")) for p in platforms.PLATFORMS])
        self.platform.currentIndexChanged.connect(self._platform_changed)
        f.addRow("Platform:", self.platform)
        self.platform_note = label("", "muted")
        f.addRow("", self.platform_note)
        self.family = combo([("debian", "Debian"), ("devuan", "Devuan (without systemd)")])
        self.suite = combo(SUITES)
        self.family.currentIndexChanged.connect(self._family_changed)
        f.addRow("Distro base:", hbox(self.family, self.suite))
        from disco.core import desktop as dsk
        des = [("", "No desktop (server, console)")] + [(d["id"], "{} ({})".format(
            d["name"], "window manager" if d["kind"] == "wm" else "desktop")) for d in dsk.catalog()["desktops"]]
        self.desktop = combo(des)
        f.addRow("GUI system:", self.desktop)
        self.init = combo(INITS)
        f.addRow("Init system:", self.init)
        self.installer = combo(INSTALLERS)
        f.addRow("Installer:", self.installer)
        self.method = combo(METHODS)
        f.addRow("Method:", self.method)
        self.mirror = QLineEdit()
        self.mirror.setPlaceholderText("default: the mirror on the Settings page")
        f.addRow("Repository:", self.mirror)
        dist.add(hbox(None, button("Save choices", self.save_choices, icon_names=("document-save",)),
                      button("Prepare", lambda: self.step("prepare"), "primary", ("system-run",))))

        self.step_btns = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for i, (key, title, desc) in enumerate(pipeline.STEPS):
            b = button("{}. {}".format(i + 1, title.replace("&", "&&")), lambda k=key: self.step(k), icon_names=())
            b.setToolTip(desc)
            b.setMinimumWidth(170)
            state = label("", "muted", wrap=False)
            self.step_btns[key] = (b, state)
            grid.addWidget(b, i, 0)
            grid.addWidget(state, i, 1)
        steps.add(grid)
        self.build_all_btn = button("Build all", self.build_all, "primary", ("media-playback-start",),
                                    "Applies what waits in Review & Apply, then runs every step that is not done "
                                    "yet (the base only when there is none).")
        self.build_all_btn.setMinimumHeight(44)
        steps.add(self.build_all_btn)
        self.rebuild = QCheckBox("Make the base system again (deletes the current system)")
        steps.add(self.rebuild)
        self.checks = label("", "muted")
        steps.add(self.checks)

        # Package lists --------------------------------------------------------------------------------
        lists = self.card("Application package lists",
                          "Installed in their order on top of the base system. Tick a list to use it; double-click "
                          "to edit it with the catalog. The files are in the lists folder of the build path.")
        self.lists = QListWidget()
        self.lists.setMinimumHeight(170)
        self.lists.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lists.itemChanged.connect(self._list_ticked)
        self.lists.itemDoubleClicked.connect(lambda _it: self.edit_list())
        lists.add(self.lists)
        lists.add(hbox(button("Add", self.add_list, icon_names=("list-add",)),
                       button("Remove", self.remove_list, icon_names=("list-remove",)),
                       button("Edit", self.edit_list, icon_names=("document-edit",)),
                       button("Up", lambda: self.move_list(-1), icon_names=("go-up",)),
                       button("Down", lambda: self.move_list(1), icon_names=("go-down",)),
                       None,
                       button("Refresh", self.refresh, icon_names=("view-refresh",)),
                       button("Log", self.show_log, icon_names=("text-x-generic",))))

        # Edit / view, after the build, tools --------------------------------------------------------------
        a, b, c = self.row(Card("Edit / view", "The parts of the system around the packages."),
                           Card("After the build", "Look inside the finished system."),
                           Card("Tools"))
        a.add(button("Repositories (sources)", lambda: self.main.go("SourcesPage"), icon_names=("software-properties",)))
        a.add(button("Overlay folder", lambda: self._open_sub("overlay"), icon_names=("folder",),
                     tooltip="Files copied into the system as they are (overlay/etc/skel/... → /etc/skel/...)"))
        a.add(button("Scripts (hooks)", lambda: self._open_sub("hooks"), icon_names=("text-x-script",),
                     tooltip="*.sh scripts run inside the system after the packages"))
        a.add(button("Tweaks: system files", lambda: self.main.go("SystemFilesPage"), icon_names=("preferences-system",),
                     tooltip="os-release, issue, motd, hostname, skel, browser policies"))
        b.add(button("Test in QEMU", self.test_qemu, icon_names=("computer",)))
        b.add(button("Terminal in the system (chroot)", self.chroot_cli, icon_names=("utilities-terminal",)))
        b.add(button("Desktop in a window (chroot GUI)", lambda: self.main.go("TerminalPage"),
                     icon_names=("video-display",)))
        b.add(button("Synaptic in the system", self.synaptic, icon_names=("synaptic", "system-software-install")))
        c.add(button("Open build folder", lambda: self._open_sub(""), icon_names=("folder-open",)))
        c.add(button("Unmount everything", self.unmount, icon_names=("media-eject",)))
        c.add(button("Delete the build (keep ISO/IMG)", lambda: self.main.keep_only_iso(), "danger",
                     ("edit-delete",)))
        c.add(button("Help (step-by-step guide)", self.help, icon_names=("help-contents",)))
        self._fill_presets()
        self._platform_changed()

    # Presets ------------------------------------------------------------------------------------------
    def _fill_presets(self, select=None):
        keep = select or self.preset.currentText()
        self.preset.blockSignals(True)
        self.preset.clear()
        for name, path, builtin in presets.available():
            self.preset.addItem(("★ " if builtin else "") + name, str(path))
        i = max(0, next((n for n in range(self.preset.count()) if self.preset.itemText(n).lstrip("★ ") == keep.lstrip("★ ")), 0))
        self.preset.setCurrentIndex(i)
        self.preset.blockSignals(False)

    def _show(self, b):
        """Put builder choices into the fields."""
        self.name.setText(b.get("distro_name", ""))
        for w, key in ((self.platform, "platform"), (self.family, "family"), (self.suite, "suite"),
                       (self.desktop, "desktop"), (self.init, "init"), (self.installer, "installer"),
                       (self.method, "method")):
            i = w.findData(b.get(key, ""))
            if i >= 0:
                w.setCurrentIndex(i)
        self.mirror.setText(b.get("mirror", ""))
        self._platform_changed()

    def _choices(self):
        b = dict((self.project.state.get("builder") if self.project else None) or {})
        b.update({"distro_name": self.name.text().strip() or "My Linux", "platform": self.platform.currentData(),
                  "family": self.family.currentData(), "suite": self.suite.currentData(),
                  "desktop": self.desktop.currentData() or "", "init": self.init.currentData(),
                  "installer": self.installer.currentData(), "method": self.method.currentData(),
                  "mirror": self.mirror.text().strip()})
        return presets.normalize({"name": "x", "builder": b})["builder"]

    def load_preset(self):
        path = self.preset.currentData()
        if not path:
            return
        try:
            pr = presets.load(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Preset", str(e))
            return
        self._show(pr["builder"])
        if self.project:
            if Lists(self.project).all() and QMessageBox.question(
                    self, "Preset", "Replace the package lists of this project with those of the preset?") != \
                    QMessageBox.StandardButton.Yes:
                self.project.state.setdefault("builder", {}).update(pr["builder"])
                self.project.save()
            else:
                presets.apply(self.project, pr)
            self.refresh()
        self.main.stage_label.setText("Preset loaded: {}".format(pr["name"]))

    def save_preset(self):
        if not self._ensure_project():
            return
        name, ok = QInputDialog.getText(self, "Save preset", "Name of the preset:",
                                        text=self.name.text().strip() or "My preset")
        if not ok or not name.strip():
            return
        try:
            self.save_choices(quiet=True)
            path = presets.save(presets.from_project(self.project, name.strip()))
        except (OSError, ValueError, PermissionError) as e:
            QMessageBox.warning(self, "Save preset", str(e))
            return
        self._fill_presets(name.strip())
        self.main.stage_label.setText("Preset saved: {}".format(path))

    def preset_file(self):
        """Import a preset file into your presets, or export the current choices to a file."""
        choice, ok = QInputDialog.getItem(self, "Preset file", "What do you want to do?",
                                          ["Import a preset file", "Export the current choices to a file"], 0, False)
        if not ok:
            return
        if choice.startswith("Import"):
            path, _ = QFileDialog.getOpenFileName(self, "Import preset", "", "Presets (*.json)")
            if path:
                try:
                    saved = presets.save(presets.load(path))
                except (OSError, ValueError) as e:
                    QMessageBox.warning(self, "Import preset", str(e))
                    return
                self._fill_presets(presets.load(saved)["name"])
        elif self._ensure_project():
            path, _ = QFileDialog.getSaveFileName(self, "Export preset", "my-preset.json", "Presets (*.json)")
            if path:
                self.save_choices(quiet=True)
                presets.save(presets.from_project(self.project, self.name.text().strip() or "My preset"), path)

    def delete_preset(self):
        name = self.preset.currentText()
        if name.startswith("★ "):
            QMessageBox.information(self, "Delete preset", "The presets of D!sco (★) cannot be deleted.")
            return
        if name and QMessageBox.question(self, "Delete preset", "Delete the preset {}?".format(name)) == \
                QMessageBox.StandardButton.Yes:
            try:
                presets.delete(name)
            except (KeyError, PermissionError, OSError) as e:
                QMessageBox.warning(self, "Delete preset", str(e))
            self._fill_presets()

    def new_preset(self):
        """Empty fields for a new distribution (and a new build folder)."""
        self._show(dict(presets.FIELDS))
        base = settings().get("general", "projects_dir")
        n = 1
        while Path(base, "distro-{}".format(n)).exists():
            n += 1
        self.folder.setText(os.path.join(base, "distro-{}".format(n)))
        self.name.setFocus()

    # Project ------------------------------------------------------------------------------------------
    def _ensure_project(self):
        """The project of the build path: opened, or created when the folder has none."""
        folder = os.path.realpath(self.folder.text().strip() or ".")
        if self.project and str(self.project.path) == folder:
            return True
        create = not Path(folder, "project.json").exists()
        if not self.main.open_project(folder, create=create, name=self.name.text().strip() or Path(folder).name):
            return False
        return True

    def save_choices(self, quiet=False):
        if not self._ensure_project():
            return False
        try:
            b = self._choices()
        except ValueError as e:
            QMessageBox.warning(self, "Builder", str(e))
            return False
        self.project.state["builder"] = b
        if not self.project.state.get("name"):
            self.project.state["name"] = b["distro_name"]
        self.project.save()
        if not quiet:
            self.main.stage_label.setText("Choices saved in {}".format(self.project.path / "project.json"))
            self.refresh()
        return True

    def project_changed(self):
        if self.project:
            self.folder.setText(str(self.project.path))
            b = self.project.state.get("builder")
            if b:
                self._show(b)
            elif self.project.state.get("name"):
                self.name.setText(self.project.state["name"])

    # Fields ---------------------------------------------------------------------------------------------
    def _platform_changed(self):
        p = platforms.get(self.platform.currentData())
        note = p.description
        if p.note:
            note += " " + p.note
        if platforms.is_foreign(p.arch):
            note += " On this {} computer its programs run through qemu-user (slower).".format(platforms.host_arch())
        self.platform_note.setText(note)
        img = p.output == "img"
        i = self.method.findData("live-build")
        self.method.model().item(i).setEnabled(not img)
        if img and self.method.currentData() == "live-build":
            self.method.setCurrentIndex(self.method.findData("disco"))
        if img and self.installer.currentData() == "calamares":
            self.installer.setCurrentIndex(self.installer.findData("none"))

    def _family_changed(self):
        devuan = self.family.currentData() == "devuan"
        i = self.init.findData("systemd")
        self.init.model().item(i).setEnabled(not devuan)
        if devuan and self.init.currentData() == "systemd":
            self.init.setCurrentIndex(self.init.findData("sysvinit"))
        if devuan and self.method.currentData() == "live-build":
            self.method.setCurrentIndex(self.method.findData("disco"))

    # Lists --------------------------------------------------------------------------------------------------
    def _lists(self):
        return Lists(self.project) if self.project else None

    def refresh(self):
        self._fill_presets()
        lst = self._lists()
        self.lists.blockSignals(True)
        self.lists.clear()
        if lst:
            for l in lst.all():
                inst, rem = l.read()
                text = "{}   —   {}{}".format(l.title, ", ".join(inst[:8]) + (" …" if len(inst) > 8 else "")
                                            or "(empty)", "   (removes {})".format(", ".join(rem)) if rem else "")
                it = QListWidgetItem("{:02d}  {}".format(l.number, text))
                it.setData(Qt.ItemDataRole.UserRole, l.name)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Checked if lst.is_on(l) else Qt.CheckState.Unchecked)
                it.setToolTip("{}\n{} package(s)\n{}".format(l.path, len(inst), l.comment()))
                self.lists.addItem(it)
            if not lst.all():
                self.lists.addItem("No lists yet: press Prepare (or Load a preset).")
        else:
            self.lists.addItem("Choose a preset or fill in the fields, then press Prepare.")
        self.lists.blockSignals(False)
        status = pipeline.Pipeline(self.project).status() if self.project else {}
        for key, (b, state) in self.step_btns.items():
            when = status.get(key, "")
            state.setText("✔ {}".format(when) if when else "")
        if self.project:
            skipped = self.project.state.get("lists", {}).get("skipped") or []
            self.checks.setText("Skipped (not in the repositories of this release/processor): {}".format(
                " ".join(skipped)) if skipped else "")

    def _current_list(self):
        it = self.lists.currentItem()
        name = it.data(Qt.ItemDataRole.UserRole) if it else None
        if not name or not self.project:
            return None
        try:
            return Lists(self.project).get(name)
        except KeyError:
            return None

    def _list_ticked(self, it):
        name = it.data(Qt.ItemDataRole.UserRole)
        if name and self.project:
            lst = Lists(self.project)
            lst.set_on(lst.get(name), it.checkState() == Qt.CheckState.Checked)

    def add_list(self):
        if not self._ensure_project():
            return
        dlg = ListEditor(self, "New list", [])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            title, names, comment = dlg.result_values()
            try:
                Lists(self.project).create(title or "New list", names, comment)
            except (ValueError, OSError) as e:
                QMessageBox.warning(self, "Package list", str(e))
            self.refresh()

    def edit_list(self):
        pl = self._current_list()
        if not pl:
            return
        dlg = ListEditor(self, pl.title, pl.packages(), pl.comment())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            title, names, comment = dlg.result_values()
            try:
                pl.write(names, title=title or pl.title, comment=comment)
                if title and title != pl.title:
                    Lists(self.project).rename(pl, title)
            except (ValueError, OSError) as e:
                QMessageBox.warning(self, "Package list", str(e))
            self.refresh()

    def remove_list(self):
        pl = self._current_list()
        if pl and QMessageBox.question(self, "Remove list", "Delete the list {}?".format(pl.name)) == \
                QMessageBox.StandardButton.Yes:
            Lists(self.project).delete(pl)
            self.refresh()

    def move_list(self, delta):
        pl = self._current_list()
        if not pl:
            return
        moved = Lists(self.project).move(pl, delta)
        self.refresh()
        for i in range(self.lists.count()):
            if moved and self.lists.item(i).data(Qt.ItemDataRole.UserRole) == moved.name:
                self.lists.setCurrentRow(i)

    def show_log(self):
        if self.project:
            from disco.gui.opener import open_url
            open_url(str(self.project.logs / "disco.log"))

    # Steps -------------------------------------------------------------------------------------------------------
    def step(self, key):
        if not self.save_choices(quiet=True):
            return
        proj = self.project
        title = dict((k, t) for k, t, _d in pipeline.STEPS)[key]
        if key == "base" and proj.has_rootfs() and QMessageBox.question(
                self, "Build base", "The project already has a system. Make a new one? Everything in it "
                                    "is replaced.") != QMessageBox.StandardButton.Yes:
            return

        def work(t):
            return pipeline.Pipeline(proj, t.set_progress, t.set_stage).run(key)

        def done(result):
            self.refresh()
            self.main.update_state()
            if key == "prepare":
                if result:
                    QMessageBox.warning(self, "Prepare", "Prepared, but fix these first:\n\n• " + "\n• ".join(result))
                else:
                    self.main.stage_label.setText("Prepared: everything is ready for 'Build base'")
            elif key == "image" and result:
                self._built(result)
        self.task(title, work, done, queue=False)

    def build_all(self):
        if not self.save_choices(quiet=True):
            return
        proj = self.project
        rebuild = self.rebuild.isChecked()
        if rebuild and proj.has_rootfs() and QMessageBox.question(
                self, "Build all", "Make the base system again? Everything in the current system is "
                                   "replaced.") != QMessageBox.StandardButton.Yes:
            return
        # What waits in Review & Apply is applied first, as part of the system.
        if self.main.pending and proj.has_rootfs():
            if QMessageBox.question(self, "Build all", "{} change(s) wait in Review & Apply. Apply them first "
                                    "(recommended)?".format(len(self.main.pending))) == QMessageBox.StandardButton.Yes:
                self.main.go("ReviewPage")
                review = next((p for p in self.main.pages if p.__class__.__name__ == "ReviewPage"), None)
                if review is not None:
                    for ch in self.main.pending:
                        ch["checked"] = True
                    review.refresh()
                    review.apply(confirm=False)
                    self.main.stage_label.setText("Applying the waiting changes: press Build all again when "
                                                  "they are done")
                    return

        def work(t):
            return pipeline.Pipeline(proj, t.set_progress, t.set_stage).build_all(rebuild_base=rebuild)

        def done(out):
            self.rebuild.setChecked(False)
            proj.mark_all_steps()
            self.refresh()
            self.main.update_state()
            if out:
                self._built(out)
        self.task("Build all", work, done, queue=False)

    def _built(self, out):
        out = Path(out)
        text = "Finished:\n{}".format(out)
        if out.suffix in (".xz", ".img"):
            from disco.core import imgbuild
            text += "\n\nWrite it to an SD card:\n{}".format(imgbuild.flash_command(out))
            text += "\n\nWARNING: dd overwrites the whole card. Check the device name with lsblk first."
        else:
            text += "\n\nWrite it to a USB stick with:\nsudo dd if='{}' of=/dev/sdX bs=4M status=progress " \
                    "oflag=sync\n\nWARNING: dd overwrites the whole stick. Check the device name with lsblk " \
                    "first.".format(out)
        QMessageBox.information(self, "Build", text)

    # After the build, tools ---------------------------------------------------------------------------------------
    def _open_sub(self, sub):
        if not self._ensure_project():
            return
        d = self.project.path / sub if sub else self.project.path
        d.mkdir(parents=True, exist_ok=True)
        from disco.gui.opener import open_url
        open_url(str(d))

    def test_qemu(self):
        if not self.project:
            return
        from disco.core import qemu
        proj = self.project
        try:
            qemu.start(proj)
        except Exception as e:  # shown to the user
            QMessageBox.warning(self, "QEMU", str(e))
            return
        self.main.stage_label.setText("QEMU started (see logs/qemu.log)")

    def _terminal(self, argv, title):
        from disco.gui.pages.terminal import terminal_command
        pkg_root = str(Path(__file__).resolve().parents[3])
        inner = ["env", "PYTHONPATH=" + pkg_root, sys.executable, "-m", "disco", "-p", str(self.project.path)] + argv
        cmd = terminal_command(inner)
        if not cmd:
            QMessageBox.warning(self, title, "No terminal emulator found. Install qterminal or xterm.")
            return
        subprocess.Popen(cmd, start_new_session=True)

    def chroot_cli(self):
        if self.project and self.project.has_rootfs():
            self._terminal(["shell"], "Terminal")

    def synaptic(self):
        """Synaptic of the system, in the live session window (it needs a display)."""
        if not (self.project and self.project.has_rootfs()):
            return
        if not (self.project.rootfs / "usr/sbin/synaptic").exists():
            if QMessageBox.question(self, "Synaptic", "Synaptic is not in the system. Add it to the list "
                                    "'My packages' and install it?") == QMessageBox.StandardButton.Yes:
                lst = Lists(self.project)
                mine = next((l for l in lst.all() if l.slug == "my-packages"), None) or lst.create("My packages")
                lst.add(mine, ["synaptic"])
                self.step("packages")
            return
        self.main.go("TerminalPage")
        self.main.stage_label.setText("Start the desktop in a window, then open Synaptic from its menu")

    def unmount(self):
        if not self.project:
            return
        if self.main.task:
            QMessageBox.information(self, "Unmount", "Wait for the running task to finish.")
            return
        from disco.core.chroot import Chroot
        Chroot(self.project.rootfs).force_release()
        self.main.stage_label.setText("Everything inside the system is unmounted")

    def help(self):
        from disco.core.config import data_file
        from disco.gui.opener import open_url
        guide = Path(data_file("guide", "Disco-Guide.pdf"))
        if not guide.exists():
            guide = Path(__file__).resolve().parents[3] / "docs" / "Disco-Guide.pdf"
        open_url(str(guide))

