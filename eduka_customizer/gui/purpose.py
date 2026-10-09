"""'What is the distribution for?' — shown when a project gets its system.

Choosing Education, Server, Professional, Home or Other lists recommendations
(desktop, login screen, compositor, look, applications, ...). Untick what you do
not want, apply them, or close the window and build everything yourself.
"""

import textwrap

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QButtonGroup, QDialog, QListWidget, QListWidgetItem, QVBoxLayout,
                                          QWidget, QGridLayout)

from eduka_customizer.core import profiles
from eduka_customizer.gui.widgets import button, combo, hbox, label, tile


class PurposeDialog(QDialog):
    def __init__(self, parent=None, current=None):
        super().__init__(parent)
        self.setWindowTitle("What is your distribution for?")
        self.setMinimumSize(820, 660)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        head = label("What is your distribution for?", wrap=False)
        head.setObjectName("pageTitle")
        lay.addWidget(head)
        lay.addWidget(label("Choose one to see recommendations for the desktop, login screen, look and "
                            "applications. Untick what you do not want, or close this window to build "
                            "everything yourself.", "muted"))
        grid = QGridLayout()
        holder = QWidget()
        holder.setLayout(grid)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tiles = {}
        for i, p in enumerate(profiles.catalog()):
            # Buttons do not wrap text: break the description into short lines.
            t = tile("{}\n{}".format(p["name"], textwrap.fill(p["description"], 58)), p["description"])
            t.setMinimumHeight(96)
            self.group.addButton(t)
            self.tiles[p["id"]] = t
            t.clicked.connect(lambda _c=False, pid=p["id"]: self.choose(pid))
            grid.addWidget(t, i // 2, i % 2)
        lay.addWidget(holder)
        lay.addWidget(label("ISO edition", "cardTitle"))
        self.edition = combo([(e["id"], "{} — {}".format(e["name"], e["description"]))
                              for e in profiles.iso_editions()], "full_apps")
        self.edition.currentIndexChanged.connect(lambda _i: self.choose(self.profile_id))
        lay.addWidget(self.edition)
        lay.addWidget(label("Recommendations", "cardTitle"))
        self.items = QListWidget()
        self.items.setMinimumHeight(170)
        self.items.setWordWrap(True)
        self.items.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(self.items)
        self.apply_btn = button("Apply ticked recommendations", self.accept, "primary")
        lay.addWidget(hbox(button("Close — I will build it myself", self.reject), None, self.apply_btn))
        self.profile_id = None
        self.choose(current or "education")

    def choose(self, profile_id):
        self.profile_id = profile_id
        self.tiles[profile_id].setChecked(True)
        self.items.clear()
        for key, text, _step in profiles.recommendations(profile_id, self.edition.currentData()):
            it = QListWidgetItem(text)
            it.setToolTip(text)
            it.setData(Qt.ItemDataRole.UserRole, key)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            self.items.addItem(it)
        empty = self.items.count() == 0
        if empty:
            self.items.addItem("Nothing is recommended: every page is yours.")
        self.apply_btn.setEnabled(not empty)

    def keys(self):
        out = []
        for i in range(self.items.count()):
            it = self.items.item(i)
            if it.data(Qt.ItemDataRole.UserRole) and it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out


def ask_purpose(page, force=False):
    """Show the dialog for the open project and apply the choice (as a background task)."""
    proj = page.project
    if not proj or not proj.has_rootfs():
        return
    if proj.state.get("purpose") and not force:
        return
    dlg = PurposeDialog(page, proj.state.get("purpose"))
    if dlg.exec() != QDialog.DialogCode.Accepted:
        proj.state["purpose"] = proj.state.get("purpose") or "other"
        proj.save()
        return
    pid, keys, edition = dlg.profile_id, dlg.keys(), dlg.edition.currentData()
    page.task("Apply recommendations for " + profiles.get(pid)["name"],
              lambda t: profiles.apply(proj, pid, keys, t.set_stage, edition=edition),
              lambda _r: page.main.update_state())
