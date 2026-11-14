"""Files: change the distribution as files and folders - in your own folders (no administrator
rights needed) or directly in the system (as administrator, here in D!sco)."""

from pathlib import Path

from disco.qt.core import Qt
from disco.qt.widgets import QTreeWidget, QTreeWidgetItem

from disco.core import permissions
from disco.gui.opener import open_url
from disco.gui.widgets import FileTreeEditor, Page, button, combo, hbox, label

FOLDERS = [
    ("overlay", "Files for the system: overlay/etc/skel/.bashrc becomes /etc/skel/.bashrc (copied with owner root)."),
    ("hooks", "Your scripts (*.sh): run inside the system, in name order, when you press 'Run my scripts'."),
    ("branding", "Your pictures and documents (wallpaper, logo...)."),
    ("debs", "Your own .deb packages (Installer step)."),
    ("iso", "The files around the system on the ISO: boot menus (boot/grub, isolinux), splash pictures."),
    ("output", "The finished ISO and SD-card images."),
]


class FilesPage(Page):
    title = "Files"
    nav_title = "Files"
    subtitle = ("Change the distribution as files and folders. Your folders can be opened and changed with your "
                "own file manager, no administrator rights needed. The system itself is edited here, as "
                "administrator.")
    icon_names = ("system-file-manager", "folder")
    CHANGES = ("Copy my files", "Run my scripts")

    def build(self):
        c = self.card("Your folders (no administrator rights needed)",
                      "They belong to you: open them in your file manager and add, change or delete anything.")
        self.folders = QTreeWidget()
        self.folders.setHeaderLabels(["Folder", "What it is for"])
        self.folders.setColumnWidth(0, 330)
        self.folders.setRootIsDecorated(False)
        self.folders.setMinimumHeight(200)
        self.folders.itemDoubleClicked.connect(lambda _it, _c: self.open_selected())
        c.add(self.folders)
        c.add(hbox(button("Open in my file manager", self.open_selected, icon_names=("folder-open",)),
                   button("Give me full access", self.share, icon_names=("emblem-shared", "folder-publicshare")),
                   None,
                   button("Run my scripts", self.run_scripts, icon_names=("system-run",)),
                   button("Copy my files into the system", self.copy_overlay, "primary")))

        s = self.card("The system (as administrator)",
                      "The files of the distribution keep their owners and permissions, because they go into the ISO "
                      "exactly as they are: a system where everyone may change every file is unsafe and does not "
                      "start correctly (sudo and SSH refuse to work). Change them here, or put your files into the "
                      "overlay folder above.")
        self.where = combo([("rootfs/etc", "/etc  (settings)"), ("rootfs/etc/skel", "/etc/skel  (new users)"),
                            ("rootfs/usr/share", "/usr/share  (pictures, themes, data)"),
                            ("rootfs/usr/local", "/usr/local  (your programs)"), ("rootfs", "/  (the whole system)"),
                            ("iso", "ISO files (boot menus)")])
        self.where.currentIndexChanged.connect(self._root_changed)
        s.add(hbox(label("Show:", wrap=False), self.where, None,
                   button("Open read-only in my file manager", self.open_system)))
        self.editor = FileTreeEditor("Select a text file on the left, change it and press 'Save file'.")
        s.add(self.editor)

    def refresh(self):
        if not self.project:
            return
        self.folders.clear()
        for name, text in FOLDERS:
            p = Path(self.project.path) / name
            it = QTreeWidgetItem([str(p), text])
            it.setData(0, Qt.ItemDataRole.UserRole, str(p))
            self.folders.addTopLevelItem(it)
        self._root_changed()

    def project_changed(self):
        self.editor.set_root(None)

    def _root_changed(self):
        if self.project:
            # The same folder again keeps the open file and what was typed (FileTreeEditor.set_root).
            self.editor.set_root(Path(self.project.path) / self.where.currentData())

    def _selected(self):
        it = self.folders.currentItem() or self.folders.topLevelItem(0)
        return Path(it.data(0, Qt.ItemDataRole.UserRole)) if it else None

    def open_selected(self):
        p = self._selected()
        if p:
            p.mkdir(parents=True, exist_ok=True)
            permissions.give_to_user(p)
            open_url(str(p))

    def share(self):
        if not self.project:
            return
        user = permissions.real_user()
        done = permissions.share_user_folders(self.project)
        self.main.stage_label.setText("Your folders belong to {} now ({} folders)".format(
            user[2] if user else "you", len(done)) if user else
            "D!sco runs without pkexec or sudo: the folders already belong to you")

    def open_system(self):
        if self.project:
            open_url(str(Path(self.project.path) / self.where.currentData()))

    def copy_overlay(self):
        from disco.core.pipeline import copy_overlay
        proj = self.project
        src = Path(proj.path) / "overlay"
        if not src.is_dir() or not any(p for p in src.rglob("*") if p.name != "README.txt"):
            self.main.stage_label.setText("The overlay folder is empty: put files into it first")
            return
        self.task("Copy my files into the system", lambda t: copy_overlay(src, proj.rootfs))

    def run_scripts(self):
        from disco.core import hooks
        proj = self.project
        scripts = [s for s in hooks.hook_dirs(proj) if s.suffix in (".sh", "")]
        if not scripts:
            self.main.stage_label.setText("The hooks folder has no scripts (*.sh)")
            return

        def work(t):
            for s in scripts:
                t.set_stage("Running " + s.name)
                hooks.run_hook(proj, s)
        self.task("Run my scripts ({})".format(len(scripts)), work)
