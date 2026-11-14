"""Wallpaper & Logo: one picture, "Set as default", Apply - for every kind of branding picture."""

from disco.qt.widgets import QCheckBox, QFileDialog, QMessageBox

from disco.core import quickbrand
from disco.gui.widgets import Card, DropZone, ImagePreview, Page, button, hbox, label


class EasyBrandPage(Page):
    title = "Wallpaper & Logo"
    nav_title = "Wallpaper & Logo"
    subtitle = ("Choose a picture (or drop it on its box), keep 'Set as default' ticked and press Apply. That is all: "
                "D!sco puts it everywhere it belongs. Pressing Apply adds the change to Review & Apply.")
    icon_names = ("preferences-desktop-wallpaper", "preferences-desktop-theme")
    CHANGES = ("Picture:",)

    def build(self):
        self.rows = {}
        for kind, title, default_text, desc in quickbrand.KINDS:
            c = Card(title, desc)
            preview = ImagePreview(192, 108)
            drop = DropZone("Drop a picture here", "Pictures (*.png *.jpg *.jpeg *.svg *.webp)", folders=False)
            drop.setMaximumHeight(96)
            drop.dropped.connect(lambda paths, k=kind: self._chosen(k, paths))
            default = QCheckBox(default_text)
            default.setChecked(True)
            default.toggled.connect(lambda on, k=kind: self._default(k, on))
            apply_btn = button("Apply", lambda k=kind: self.apply(k), "primary")
            c.add(hbox(preview, drop))
            c.add(hbox(default, None, button("Choose...", lambda k=kind: self._choose(k)), apply_btn))
            self.add(c)
            self.rows[kind] = (preview, default, apply_btn)
        self.add(hbox(label("Want more? Login screen themes, Plymouth themes and a branding package are in the "
                            "other tabs of this step.", "muted"), None,
                      button("Apply all chosen pictures", self.apply_all)))

    def refresh(self):
        if not self.project:
            return
        for kind, (preview, default, apply_btn) in self.rows.items():
            pic = quickbrand.stored(self.project, kind)
            preview.show_file(str(pic) if pic else "")
            default.blockSignals(True)
            default.setChecked(quickbrand.is_default(self.project, kind))
            default.blockSignals(False)
            apply_btn.setEnabled(pic is not None)

    def _choose(self, kind):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a picture", "", "Pictures (*.png *.jpg *.jpeg *.svg *.webp)")
        if path:
            self._chosen(kind, [path])

    def _chosen(self, kind, paths):
        if not self.project or not paths:
            return
        try:
            quickbrand.store(self.project, kind, paths[0], self.rows[kind][1].isChecked())
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Picture", str(e))
            return
        self.refresh()
        self.main.stage_label.setText("Picture chosen: press Apply to use it")

    def _default(self, kind, on):
        st = (self.project.state.setdefault("quickbrand", {}).get(kind)) if self.project else None
        if st is not None:
            st["default"] = bool(on)
            self.project.save()

    def _snapshot(self, kind):
        """The picture and 'Set as default' of this moment, kept for the waiting change."""
        try:
            return quickbrand.snapshot(self.project, kind)
        except (ValueError, OSError) as e:
            QMessageBox.information(self, "Picture", str(e))
            return None

    def apply(self, kind):
        if not self.project or quickbrand.stored(self.project, kind) is None:
            QMessageBox.information(self, "Picture", "Choose a picture first.")
            return
        snap = self._snapshot(kind)
        if snap is None:
            return
        image, default = snap
        proj = self.project
        title = dict((k, t) for k, t, *_ in quickbrand.KINDS)[kind]
        self.task("Picture: {}{} ({})".format(title, "" if default else " added", image.name),
                  lambda t: quickbrand.apply(proj, kind, image, default))

    def apply_all(self):
        chosen = [k for k in self.rows if self.project and quickbrand.stored(self.project, k)]
        if not chosen:
            QMessageBox.information(self, "Pictures", "Choose at least one picture first.")
            return
        snaps = []
        for k in chosen:
            snap = self._snapshot(k)
            if snap is None:
                return
            snaps.append((k,) + snap)
        proj = self.project

        def work(t):
            for kind, image, default in snaps:
                t.set_stage("Picture: " + kind)
                quickbrand.apply(proj, kind, image, default)
        self.task("Picture: all chosen ({})".format(", ".join(k for k, *_ in snaps)), work)
