"""System files: os-release, lsb-release, issue, hostname, hosts, motd; the user skeleton;
the GRUB background of installed systems."""

from disco.qt.widgets import QFileDialog, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit

from disco.core import sysfiles
from disco.gui.widgets import FilePicker, ImagePreview, Page, button, hbox, label


class SystemFilesPage(Page):
    title = "System files"
    nav_title = "System files"
    subtitle = ("The files that tell who the system is, edited directly: os-release, lsb-release, issue (\"Welcome "
                "to ...\"), issue.net, hostname, hosts and motd. \"Template\" fills a file from the Identity page. "
                "Your changes wait in Review & Apply.")
    icon_names = ("text-x-generic", "preferences-system")
    CHANGES = ("Write /etc", "User picture", "Copy settings", "GRUB background")

    def build(self):
        c = self.card("Identity files")
        self.files = QListWidget()
        self.files.setMaximumWidth(200)
        for rel, title, _d in sysfiles.FILES:
            self.files.addItem("/" + rel)
        self.files.currentRowChanged.connect(self._show)
        self.desc = label("", "muted")
        self.editor = QPlainTextEdit()
        self.editor.setMinimumHeight(240)
        from disco.qt.gui import QFontDatabase
        self.editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        right = hbox(self.files, self.editor)
        c.add(right)
        c.add(self.desc)
        c.add(hbox(button("Template from Identity", self.template, icon_names=("document-new",)),
                   button("Reload", self._reload, icon_names=("view-refresh",)), None,
                   button("Save to the system", self.save, "primary", ("document-save",))))

        s = self.card("New users (/etc/skel)", "What every new user starts with. The bash prompt and the message after "
                                                "login are on Look & Feel → Terminal & Browser.")
        self.face = FilePicker("User picture", "Images (*.png *.jpg *.jpeg *.svg)")
        self.face_preview = ImagePreview(96, 96)
        self.face.changed.connect(self.face_preview.show_file)
        s.add(hbox(label("Picture of new users (.face, also the login screen's default picture):"), self.face,
                   self.face_preview, button("Use it", self.set_face)))
        self.config_dir = FilePicker("Settings folder of this computer", directory=True)
        self.config_dir.setText("")
        self.into = QLineEdit(".config")
        self.into.setMaximumWidth(140)
        s.add(label("Copy a settings folder of this computer into /etc/skel, for example ~/.config/xfce4 (panels, "
                    "keyboard shortcuts) - caches, histories and keys are left out:", "muted"))
        s.add(hbox(self.config_dir, label("into /etc/skel/", wrap=False), self.into,
                   button("Copy", self.import_config)))

        g = self.card("GRUB of installed computers", "The background of the GRUB menu of computers installed from the "
                                                     "ISO (GRUB_BACKGROUND; the installer runs update-grub). The menu "
                                                     "of the ISO itself is on Boot → Boot Menu.")
        self.grub = FilePicker("GRUB background", "Images (*.png *.jpg *.jpeg)")
        self.grub_preview = ImagePreview(192, 108)
        self.grub.changed.connect(self.grub_preview.show_file)
        self._queued = {}      # (project, file): text of a change that waits in Review & Apply
        g.add(hbox(self.grub, self.grub_preview, button("Use it", self.set_grub),
                   button("Remove", self.clear_grub, "danger")))

    # Files ------------------------------------------------------------------------------------------------
    def _rel(self):
        row = self.files.currentRow()
        return sysfiles.FILES[row][0] if row >= 0 else None

    def _show(self, row):
        if row < 0 or not self.project:
            return
        rel, _title, desc = sysfiles.FILES[row]
        key = (str(self.project.path), rel)
        if key in self._queued and not any(ch.get("name") == "Write /" + rel for ch in self.main.pending_for(self)):
            self._queued.pop(key)          # applied, or taken out of Review & Apply
        queued = self._queued.get(key)
        self.desc.setText(desc + ("  <b>(your change waits in Review & Apply)</b>" if queued is not None else ""))
        if queued is not None:
            text = queued
        else:
            try:
                text = sysfiles.read(self.project, rel)
            except ValueError as e:
                text = "# " + str(e)
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)

    def _reload(self):
        self._show(self.files.currentRow())

    def project_changed(self):
        self.editor.document().setModified(False)
        self._reload()

    def refresh(self):
        if self.files.currentRow() < 0:
            self.files.setCurrentRow(0)
        elif not self.editor.document().isModified():   # never throw away what is being typed
            self._reload()

    def template(self):
        rel = self._rel()
        if rel and self.project:
            self.editor.setPlainText(sysfiles.template(self.project, rel))

    def save(self):
        rel = self._rel()
        if not rel or not self.project:
            return
        text = self.editor.toPlainText()
        try:
            sysfiles.check(rel, text)
        except ValueError as e:
            QMessageBox.warning(self, "System files", str(e))
            return
        proj = self.project
        key = (str(proj.path), rel)
        self._queued[key] = text
        self.editor.document().setModified(False)
        self.task("Write /" + rel, lambda t: sysfiles.write(proj, rel, text),
                  lambda _r: self._queued.pop(key, None))

    # Skel ---------------------------------------------------------------------------------------------------
    def set_face(self):
        img = self.face.text()
        if not img:
            return
        proj = self.project
        self.task("User picture for new users", lambda t: sysfiles.set_face(proj, img))

    def import_config(self):
        folder, into = self.config_dir.text(), self.into.text().strip() or ".config"
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "Settings folder", "")
            if not folder:
                return
            self.config_dir.setText(folder)
        proj = self.project
        self.task("Copy settings {} into /etc/skel".format(folder), lambda t: sysfiles.import_config(proj, folder, into))

    def set_grub(self):
        img = self.grub.text()
        if img:
            proj = self.project
            self.task("GRUB background of installed systems", lambda t: sysfiles.set_grub_background(proj, img))

    def clear_grub(self):
        proj = self.project
        self.task("GRUB background removed", lambda t: sysfiles.clear_grub_background(proj))
