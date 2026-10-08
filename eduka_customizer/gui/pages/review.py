"""Review & Apply: every change chosen in the steps before waits here. Check each
one (or go back and change it), then apply them all at once."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import QListWidget, QListWidgetItem, QMessageBox

from eduka_customizer.gui.widgets import Page, button, hbox, label


def summary(project):
    """[(topic, value)] of what the ISO will have, from the project."""
    st = project.state
    ident = st.get("identity", {})
    out = [("Name", "{} {}".format(ident.get("name") or project.display_name(), ident.get("version", "")).strip()),
           ("Live user", ident.get("live_user") or "user (Debian default)"),
           ("Language", (st.get("locale") or {}).get("default") or "as in the ISO"),
           ("Time zone", (st.get("locale") or {}).get("timezone") or "")]
    d = st.get("desktop") or {}
    if d.get("id"):
        out.append(("Desktop", "{} ({})".format(d["id"], d.get("edition", "full"))))
    if st.get("purpose"):
        out.append(("Purpose", "{} ({})".format(st["purpose"], st.get("iso_edition", "full"))))
    if st.get("default_apps"):
        out.append(("Default applications", ", ".join("{}: {}".format(k, v) for k, v in st["default_apps"].items())))
    if st.get("sounds"):
        out.append(("System sounds", st["sounds"].get("theme", "")))
    if st.get("welcome", {}).get("enabled"):
        out.append(("Welcome screen", st["welcome"].get("title", "")))
    boot = st.get("boot") or {}
    if boot.get("grub_theme"):
        out.append(("GRUB theme", boot["grub_theme"]))
    if boot.get("installed_loader"):
        out.append(("Boot loader of installed systems", boot["installed_loader"]))
    return [(k, v) for k, v in out if v]


class ReviewPage(Page):
    title = "Review & Apply"
    nav_title = "Review & Apply"
    subtitle = ("Step 14 · Everything you chose waits here. Tick each change when you are sure, or go back and "
                "change it. Then apply them all at once.")
    icon_names = ("checkbox", "dialog-ok")

    def build(self):
        c = self.card("Changes waiting to be applied")
        self.items = QListWidget()
        self.items.setMinimumHeight(260)
        self.items.itemChanged.connect(lambda _i: self._update())
        c.add(self.items)
        self.state = label("", "muted")
        c.add(self.state)
        c.add(hbox(button("Tick all", self.tick_all), button("Go back and change it", self.go_back),
                   button("Remove from the list", self.remove, "danger"), None,
                   button("Up", lambda: self.move(-1)), button("Down", lambda: self.move(1))))
        self.apply_btn = button("Apply all changes", self.apply, "primary")
        self.apply_btn.setMinimumHeight(40)
        c.add(hbox(label("Changes run in this order. A failed change stops the rest; nothing is lost.", "muted"),
                   None, self.apply_btn))

        c = self.card("Your distribution so far")
        self.summary = label("", "muted")
        c.add(self.summary)

    # -------------------------------------------------------------------------------
    def refresh(self):
        self.items.blockSignals(True)
        self.items.clear()
        for n, ch in enumerate(self.main.pending, 1):
            it = QListWidgetItem("{}. {}   —   {}".format(n, ch["name"], ch["section"] or "step"))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if ch["checked"] else Qt.CheckState.Unchecked)
            self.items.addItem(it)
        self.items.blockSignals(False)
        if self.project:
            self.summary.setText("<br>".join("<b>{}</b>: {}".format(k, v) for k, v in summary(self.project)))
        self._update()

    def _update(self):
        for i, ch in enumerate(self.main.pending):
            it = self.items.item(i)
            if it is not None:
                ch["checked"] = it.checkState() == Qt.CheckState.Checked
        n, ticked = len(self.main.pending), sum(1 for c in self.main.pending if c["checked"])
        if not n:
            self.state.setText("Nothing is waiting. The changes you choose in steps 2 to 13 are collected here.")
        else:
            self.state.setText("{} of {} change(s) checked{}".format(
                ticked, n, "" if ticked == n else " — tick every change you are sure about to apply them"))
        self.apply_btn.setEnabled(n > 0 and ticked == n)
        self.main._update_pending()

    def tick_all(self):
        for i in range(self.items.count()):
            self.items.item(i).setCheckState(Qt.CheckState.Checked)

    def _row(self):
        row = self.items.currentRow()
        return row if 0 <= row < len(self.main.pending) else None

    def go_back(self):
        row = self._row()
        if row is not None and self.main.pending[row]["page"]:
            self.main.go(self.main.pending[row]["page"])

    def remove(self):
        row = self._row()
        if row is not None:
            del self.main.pending[row]
            self.refresh()

    def move(self, step):
        row = self._row()
        if row is None or not 0 <= row + step < len(self.main.pending):
            return
        p = self.main.pending
        p[row], p[row + step] = p[row + step], p[row]
        self.refresh()
        self.items.setCurrentRow(row + step)

    def apply(self):
        changes = list(self.main.pending)
        if QMessageBox.question(self, "Review & Apply", "Apply {} change(s) to the image now?".format(len(changes))) \
                != QMessageBox.StandardButton.Yes:
            return
        state = {"done": 0}

        def work(t):
            results = []
            for n, ch in enumerate(changes, 1):
                t.set_stage("{}/{}: {}".format(n, len(changes), ch["name"]))
                results.append(ch["func"](t))
                state["done"] = n
            return results

        def done(results):
            for ch, res in zip(changes, results):
                if ch["done"]:
                    try:
                        ch["done"](res)
                    except Exception:  # a page callback must not stop the others
                        pass
            del self.main.pending[:len(changes)]
            self.refresh()
            if QMessageBox.question(self, "Review & Apply", "All {} change(s) were applied. Continue to Check & "
                                    "Build?".format(len(changes))) == QMessageBox.StandardButton.Yes:
                self.main.next_step(self.section, self.main.steps[self.section.step])
        task = self.task("Apply all changes", work, done)
        if task is not None:
            # A failed change: the ones before it are applied and leave the list, the rest stay.
            task.done.connect(lambda ok, _r, _e: (None if ok else self._after_failure(state["done"])))

    def _after_failure(self, applied):
        del self.main.pending[:applied]
        self.refresh()
