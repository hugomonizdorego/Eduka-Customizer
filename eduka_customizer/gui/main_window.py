"""Main window: sidebar navigation, pages, task status and log console."""

import logging
import time

from eduka_customizer.qt.core import QSize, Qt, QTimer
from eduka_customizer.qt.gui import QAction, QFont, QKeySequence, QTextCharFormat, QColor
from eduka_customizer.qt.widgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                             QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from eduka_customizer import APP_NAME, VERSION_LABEL
from eduka_customizer.core import runner
from eduka_customizer.core.config import settings
from eduka_customizer.core.log import OUTPUT, add_file_handler, get_logger, remove_handler
from eduka_customizer.core.project import Project, ProjectLocked
from eduka_customizer.gui import style
from eduka_customizer.gui.widgets import icon
from eduka_customizer.gui.worker import LogBridge, QtLogHandler, Task


# Bundled Papirus icons (GPL-3.0), see data/icons/menu/README.md.
MENU_ICONS = {"ProjectPage": "project", "WizardPage": "wizard", "SourcesPage": "sources",
              "IdentityPage": "identity", "UsersPage": "users", "LanguagePage": "language",
              "PackagesPage": "packages", "FlatpakPage": "flatpak", "ReplaceAppsPage": "replace",
              "KernelPage": "kernel", "DesktopPage": "desktop", "ThemesPage": "themes",
              "AppearancePage": "wallpaper", "PlymouthPage": "plymouth", "BrandingPage": "branding",
              "CalamaresPage": "calamares", "BootMenuPage": "bootmenu", "WorkshopPage": "workshop",
              "TerminalPage": "terminal", "BuildPage": "build", "SettingsPage": "settings", "SoundsPage": "sounds",
              "WelcomePage": "welcome", "GrubDesignPage": "bootmenu", "AboutPage": "about"}

# The sidebar, in the order of the work. Pages that are used together share one
# menu (as tabs). (key, menu title, icon, page classes, is a numbered step)
SECTIONS = [
    ("start", "Start", "project", ["project.ProjectPage"], True),
    ("wizard", "Quick Wizard", "wizard", ["wizard.WizardPage"], False),
    ("sources", "Repositories", "sources", ["sources.SourcesPage"], True),
    ("identity", "Identity & Branding", "identity", ["identity.IdentityPage", "branding.BrandingPage"], True),
    ("users", "Users", "users", ["users.UsersPage"], True),
    ("language", "Language", "language", ["language.LanguagePage"], True),
    ("desktop", "Desktop", "desktop", ["desktop.DesktopPage"], True),
    ("software", "Software", "packages", ["packages.PackagesPage", "flatpak.FlatpakPage",
                                          "replace_apps.ReplaceAppsPage"], True),
    ("boot", "Kernel & Boot", "kernel", ["kernel.KernelPage", "bootmenu.BootMenuPage", "grubdesign.GrubDesignPage"],
     True),
    ("look", "Look & Feel", "themes", ["themes.ThemesPage", "appearance.AppearancePage",
                                       "plymouth.PlymouthPage"], True),
    ("sounds", "System Sounds", "sounds", ["sounds.SoundsPage"], True),
    ("welcome", "Welcome Screen", "welcome", ["welcome.WelcomePage"], True),
    ("installer", "Installer", "calamares", ["calamares.CalamaresPage"], True),
    ("advanced", "Advanced", "terminal", ["terminal.TerminalPage", "workshop.WorkshopPage"], True),
    ("build", "Check & Build", "build", ["build.BuildPage"], True),
    ("settings", "Settings", "settings", ["settings_page.SettingsPage"], False),
    ("about", "About", "about", ["about.AboutPage"], False),
]


class Section(QWidget):
    """One menu of the sidebar: a page, or several related pages as tabs, and the
    Back / Next step bar of the step-by-step build."""

    def __init__(self, main, key, title, pages, step):
        super().__init__()
        from eduka_customizer.qt.widgets import QTabWidget
        self.main, self.key, self.title, self.pages, self.step = main, key, title, pages, step
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.tabs = None
        if len(pages) > 1:
            self.tabs = QTabWidget()
            self.tabs.setObjectName("sectionTabs")
            self.tabs.setDocumentMode(True)
            for page in pages:
                name = page.nav_title if hasattr(page, "nav_title") else page.title
                self.tabs.addTab(page, menu_icon(MENU_ICONS.get(page.__class__.__name__), *page.icon_names),
                                 name.replace("&", "&&"))
            self.tabs.currentChanged.connect(lambda _i: self.refresh())
            lay.addWidget(self.tabs, 1)
        else:
            lay.addWidget(pages[0], 1)
        for page in pages:
            page.section = self
        self.bar = None

    @property
    def needs_rootfs(self):
        return all(p.needs_rootfs for p in self.pages)

    def current(self):
        return self.tabs.currentWidget() if self.tabs else self.pages[0]

    def show_page(self, page):
        if self.tabs:
            self.tabs.setCurrentWidget(page)

    def refresh(self):
        self.current().refresh()

    def add_bar(self, prev, nxt):
        from eduka_customizer.gui.widgets import button
        bar = QFrame()
        bar.setObjectName("stepBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(28, 8, 28, 10)
        if prev:
            h.addWidget(button("◀  Back: {}. {}".format(prev.step, prev.title.replace("&", "&&")),
                               lambda: self.main.go_section(prev)))
        self.state = QLabel("")
        self.state.setObjectName("muted")
        h.addStretch(1)
        h.addWidget(self.state)
        if nxt:
            self.next_btn = button("Done — next step: {}. {}  ▶".format(nxt.step, nxt.title.replace("&", "&&")),
                                   lambda: self.main.next_step(self, nxt), "primary")
            h.addWidget(self.next_btn)
        else:
            self.next_btn = None
        self.layout().addWidget(bar)
        self.bar = bar


def menu_icon(key, *fallback):
    """The bundled menu icon, or the icon theme's when it is missing."""
    from eduka_customizer.qt.gui import QIcon
    from eduka_customizer.core.config import data_file
    if key:
        path = data_file("icons", "menu", key + ".svg")
        if path.exists():
            return QIcon(str(path))
    return icon(*fallback)


def app_icon():
    from eduka_customizer.qt.gui import QIcon
    from eduka_customizer.core.config import data_file
    ic = icon("distroforge")
    if ic.isNull():
        for path in (data_file("icons", "distroforge.svg"),
                     data_file("..", "icons", "distroforge.svg")):
            if path.exists():
                return QIcon(str(path))
    return ic


class MainWindow(QMainWindow):
    def __init__(self, dark=False):
        super().__init__()
        self.dark = dark
        self.project = None
        self.task = None
        self.live = None
        self._file_handler = None
        self._task_started = 0
        self.setWindowTitle("{} {}".format(APP_NAME, VERSION_LABEL))
        self.setWindowIcon(app_icon())
        self.resize(1280, 860)

        self.bridge = LogBridge()
        self.bridge.message.connect(self._append_log)
        self.bridge.crashed.connect(self._show_crash)
        from eduka_customizer.core import log as logmod
        logmod.on_unhandled_error(lambda t, e, tb: self.bridge.crashed.emit("{}: {}".format(t.__name__, e)))
        self.log_handler = QtLogHandler(self.bridge)
        self.log_handler.setLevel(OUTPUT)  # debug details go to /tmp/distroforge
        get_logger().addHandler(self.log_handler)
        get_logger().setLevel(logging.DEBUG)

        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._sidebar())

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(0)
        lay.addWidget(right, 1)

        self.header = self._header()
        rlay.addWidget(self.header)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        self.splitter.addWidget(self.log)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([700, 120])
        self._sized = False
        rlay.addWidget(self.splitter, 1)
        rlay.addWidget(self._status())

        self._build_pages()
        self._actions()
        self.apply_style()
        self.update_state()

    # Layout ------------------------------------------------------------
    def _sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(240)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 0, 0, 10)
        v.setSpacing(0)
        brand = QLabel("DistroForge")
        brand.setObjectName("brand")
        v.addWidget(brand)
        sub = QLabel("{} · ISO builder for Debian-based distributions".format(VERSION_LABEL))
        sub.setObjectName("brandSub")
        sub.setWordWrap(True)
        v.addWidget(sub)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setIconSize(QSize(22, 22))
        self.nav.currentRowChanged.connect(self._show_page)
        v.addWidget(self.nav, 1)
        donate = QPushButton("♥  Support {}".format(APP_NAME))
        donate.setObjectName("sideDonate")
        donate.setToolTip("Donate with PayPal: a gift keeps the project going")
        donate.clicked.connect(self._donate)
        v.addWidget(donate)
        self.theme_btn = QPushButton("Dark mode")
        self.theme_btn.setObjectName("sideButton")
        self.theme_btn.clicked.connect(self.toggle_theme)
        v.addWidget(self.theme_btn)
        return side

    def _donate(self):
        from eduka_customizer import DONATE_URL
        from eduka_customizer.gui.pages.about import open_url
        open_url(DONATE_URL)

    def _header(self):
        h = QFrame()
        h.setObjectName("headerBar")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(28, 12, 20, 12)
        self.project_label = QLabel("No project open")
        f = QFont()
        f.setBold(True)
        self.project_label.setFont(f)
        lay.addWidget(self.project_label)
        self.distro_badge = QLabel("")
        self.distro_badge.setObjectName("badge")
        lay.addWidget(self.distro_badge)
        lay.addStretch(1)
        # Where you are in the build: "Step 6 of 14 · Desktop" and a thin progress bar.
        box = QVBoxLayout()
        box.setSpacing(4)
        self.step_label = QLabel("")
        self.step_label.setObjectName("stepLabel")
        box.addWidget(self.step_label)
        self.step_progress = QProgressBar()
        self.step_progress.setObjectName("stepProgress")
        self.step_progress.setTextVisible(False)
        self.step_progress.setFixedWidth(220)
        box.addWidget(self.step_progress)
        lay.addLayout(box)
        self.mount_badge = QLabel("")
        self.mount_badge.setObjectName("badgeWarn")
        self.mount_badge.setVisible(False)
        lay.addWidget(self.mount_badge)
        return h

    def _status(self):
        s = QFrame()
        s.setObjectName("statusBar")
        lay = QHBoxLayout(s)
        lay.setContentsMargins(20, 8, 20, 8)
        self.stage_label = QLabel("Ready")
        lay.addWidget(self.stage_label, 1)
        self.elapsed = QLabel("")
        self.elapsed.setObjectName("muted")
        lay.addWidget(self.elapsed)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(260)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_task)
        lay.addWidget(self.cancel_btn)
        self.log_btn = QPushButton("Hide log")
        self.log_btn.clicked.connect(self.toggle_log)
        lay.addWidget(self.log_btn)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        return s

    def _build_pages(self):
        import importlib
        self.pages, self.sections, self.steps = [], [], []
        for key, title, icon_key, classes, is_step in SECTIONS:
            pages = []
            for dotted in classes:
                mod, cls = dotted.split(".")
                page = getattr(importlib.import_module("eduka_customizer.gui.pages." + mod), cls)(self)
                pages.append(page)
                self.pages.append(page)
            sec = Section(self, key, title, pages, len(self.steps) + 1 if is_step else 0)
            for page in pages:
                page.step = sec.step
            if is_step:
                self.steps.append(sec)
            self.sections.append(sec)
            self.stack.addWidget(sec)
            item = QListWidgetItem(menu_icon(icon_key, *pages[0].icon_names), self._nav_text(sec))
            self.nav.addItem(item)
        # Back / "Done — next step" under every step, from the source to the ISO.
        for n, sec in enumerate(self.steps):
            sec.add_bar(self.steps[n - 1] if n else None, self.steps[n + 1] if n + 1 < len(self.steps) else None)
        self.nav.setCurrentRow(0)

    @staticmethod
    def _nav_text(sec, done=False):
        if not sec.step:
            return sec.title
        return "{}. {}{}".format(sec.step, sec.title, "  ✔" if done else "")

    def _actions(self):
        quit_ = QAction("Quit", self)
        quit_.setShortcut(QKeySequence.StandardKey.Quit)
        quit_.triggered.connect(self.close)
        self.addAction(quit_)
        for i in range(min(9, len(self.sections))):
            a = QAction(self)
            a.setShortcut(QKeySequence("Ctrl+{}".format(i + 1)))
            a.triggered.connect(lambda _=False, n=i: self.nav.setCurrentRow(n))
            self.addAction(a)

    def apply_style(self):
        from eduka_customizer.qt.widgets import QApplication
        app = QApplication.instance()
        app.setPalette(style.palette(self.dark))
        app.setStyleSheet(style.stylesheet(self.dark))
        self.theme_btn.setText("Light mode" if self.dark else "Dark mode")

    def toggle_theme(self):
        self.dark = not self.dark
        self.apply_style()
        cfg = settings()
        cfg.set("general", "theme", "dark" if self.dark else "light")
        try:
            cfg.save()
        except OSError:
            pass

    def toggle_log(self):
        visible = not self.log.isVisible()
        self.log.setVisible(visible)
        self.log_btn.setText("Hide log" if visible else "Show log")

    # Navigation ------------------------------------------------------------
    def free_navigation(self):
        return settings().getbool("general", "free_navigation")

    def first_open_step(self):
        """The first step that is not done yet (its menu and all before it are open)."""
        p = self.project
        for sec in self.steps:
            if sec.key == "start":
                if not (p and p.has_rootfs()):
                    return sec
                continue
            if not p.step_done(sec.key):
                return sec
        return None

    def section_open(self, sec):
        has = bool(self.project and self.project.has_rootfs())
        if sec.needs_rootfs and not has:
            return False
        if not sec.step or self.free_navigation():
            return True
        first = self.first_open_step()
        return first is None or sec.step <= first.step

    def _show_page(self, row):
        if row < 0:
            return
        sec = self.sections[row]
        if not self.section_open(sec):
            first = self.first_open_step()
            if sec.needs_rootfs and not (self.project and self.project.has_rootfs()):
                self.stage_label.setText("Open or create a project with a system first (step 1)")
            elif first:
                self.stage_label.setText("Finish step {}. {} first (press 'Done — next step')".format(
                    first.step, first.title))
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(self.stack.currentIndex())
            self.nav.blockSignals(False)
            return
        self.stack.setCurrentIndex(row)
        self._update_step_header()
        try:
            sec.refresh()
        except Exception as e:  # a broken page must not take the window down
            get_logger().error("Could not refresh %s: %s", sec.title, e)

    def _update_step_header(self):
        if not hasattr(self, "step_label"):
            return
        sec = self.stack.currentWidget()
        total = len(self.steps)
        done = 0
        if self.project:
            for st in self.steps:
                if (self.project.has_rootfs() if st.key == "start" else self.project.step_done(st.key)):
                    done += 1
        self.step_progress.setRange(0, max(1, total))
        self.step_progress.setValue(done)
        if sec is not None and getattr(sec, "step", 0):
            self.step_label.setText("Step {} of {} · {}  —  {} done".format(sec.step, total, sec.title, done))
        elif sec is not None:
            self.step_label.setText("{}  —  {} of {} steps done".format(sec.title, done, total))

    def go_section(self, sec):
        self.nav.setCurrentRow(self.sections.index(sec))

    def go(self, page_class_name):
        for sec in self.sections:
            for p in sec.pages:
                if p.__class__.__name__ == page_class_name:
                    if not self.section_open(sec):
                        self.stage_label.setText("{} opens at step {}".format(sec.title, sec.step))
                        return
                    sec.show_page(p)
                    self.go_section(sec)
                    if self.stack.currentWidget() is sec:
                        sec.refresh()
                    return

    def next_step(self, sec, nxt):
        """'Done — next step': mark this step done and open the next one."""
        if not self.project:
            return
        if sec.key == "start" and not self.project.has_rootfs():
            QMessageBox.information(self, APP_NAME, "Step 1 is done when the project has a system: extract an "
                                    "ISO, bootstrap Debian or snapshot this computer.")
            return
        self.project.mark_step(sec.key)
        self.update_state()
        self.go_section(nxt)

    def update_state(self):
        for i, sec in enumerate(self.sections):
            item = self.nav.item(i)
            enabled = self.section_open(sec)
            flags = item.flags()
            item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags & ~Qt.ItemFlag.ItemIsEnabled)
            done = bool(sec.step and self.project and (self.project.has_rootfs() if sec.key == "start"
                                                       else self.project.step_done(sec.key)))
            item.setText(self._nav_text(sec, done and not (self.project and "*" in
                                                           self.project.state.get("steps_done", []))))
            item.setToolTip("" if enabled else "Opens after step {}".format(max(1, sec.step - 1)))
            if sec.bar is not None:
                sec.bar.setVisible(bool(self.project))
                if sec.next_btn is not None:
                    sec.next_btn.setEnabled(bool(self.project and self.project.has_rootfs()))
                sec.state.setText("✔ done" if done else "")
        self._update_step_header()
        if self.project:
            path = str(self.project.path)
            short = path if len(path) <= 48 else "…" + path[-46:]
            self.project_label.setText("{}  —  {}".format(self.project.state.get("name") or
                                                         self.project.display_name(), short))
            self.project_label.setToolTip(path)
            d = self.project.distro
            self.distro_badge.setText(d.summary() if d.id else "empty project")
            self.distro_badge.setVisible(True)
        else:
            self.project_label.setText("No project open")
            self.distro_badge.setVisible(False)
        self._update_mounts()

    def _update_mounts(self):
        from eduka_customizer.core.chroot import mounts_under
        n = len(mounts_under(self.project.rootfs)) if self.project else 0
        self.mount_badge.setText("{} mounts active in the image".format(n))
        self.mount_badge.setVisible(n > 0 and not self.task)

    # Project ------------------------------------------------------------------
    def open_project(self, path, create=False, name=None):
        if self.task:
            QMessageBox.information(self, APP_NAME, "Wait for the running task to finish.")
            return False
        try:
            proj = Project.create(path, name) if create else Project.open(path)
            proj.lock()
        except ProjectLocked as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return False
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, APP_NAME, "Could not open project:\n{}".format(e))
            return False
        self.close_project()
        self.project = proj
        self._file_handler = add_file_handler(proj.logs / "distroforge.log")
        settings().add_recent(proj.path)
        get_logger().info("Opened project %s", proj.path)
        self.update_state()
        for p in self.pages:
            if hasattr(p, "project_changed"):
                p.project_changed()
        return True

    def close_project(self):
        if self.live and self.live.running:
            self.live.stop()
        self.live = None
        if self.project:
            self.project.unlock()
            if self._file_handler:
                remove_handler(self._file_handler)
                self._file_handler = None
        self.project = None

    # Tasks ----------------------------------------------------------------------
    def run_task(self, name, func, done=None):
        """Run func(task) in a thread. done(result) runs in the GUI on success."""
        if self.task:
            QMessageBox.information(self, APP_NAME, "'{}' is still running. Please wait or cancel it."
                                    .format(self.task.name))
            return None
        task = Task(name, func, self)
        self.task = task
        self.stage_label.setText(name + "...")
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self._task_started = time.time()
        self.timer.start(1000)
        task.progress.connect(self._on_progress)
        task.stage.connect(lambda s: self.stage_label.setText(s))
        task.done.connect(lambda ok, res, err: self._on_done(task, ok, res, err, done))
        if not self.log.isVisible():
            self.toggle_log()
        get_logger().info("▶ %s", name)
        task.start()
        return task

    def _on_progress(self, pct):
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 1000)
        self.progress.setValue(int(pct * 10))
        self.progress.setFormat("{:.0f}%".format(pct))

    def _tick(self):
        if self.task:
            secs = int(time.time() - self._task_started)
            self.elapsed.setText("{}:{:02d}".format(secs // 60, secs % 60))

    def _on_done(self, task, ok, result, error, done):
        self.task = None
        self.timer.stop()
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        if self.project:
            try:
                self.project.load()
            except (OSError, ValueError):
                pass
        if ok:
            self.stage_label.setText("{} — finished".format(task.name))
            get_logger().info("✔ %s finished", task.name)
            if done:
                try:
                    done(result)
                except Exception as e:
                    get_logger().error("%s", e)
        else:
            self.stage_label.setText("{} — failed".format(task.name))
            get_logger().error("✘ %s: %s", task.name, error)
            QMessageBox.warning(self, task.name, error[-3000:])
        self.update_state()
        page = self.stack.currentWidget()
        if page:
            try:
                page.refresh()
            except Exception as e:
                get_logger().error("%s", e)

    def cancel_task(self):
        if self.task:
            runner.CANCEL.set()
            self.cancel_btn.setEnabled(False)
            self.stage_label.setText("Canceling...")

    # Log ------------------------------------------------------------------------
    def _append_log(self, level, text):
        c = style.colors(self.dark)
        color = {logging.WARNING: c["warn"], logging.ERROR: c["error"],
                 logging.CRITICAL: c["error"], OUTPUT: "#8fb3a8",
                 logging.DEBUG: "#6f8a83"}.get(level, "#e6f5ef")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self.log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _show_crash(self, text):
        from eduka_customizer.core import log as logmod
        QMessageBox.critical(self, "Unexpected error",
                             "{}\n\nThe details were written to {}.\nPlease send that file to the "
                             "developers (Settings → Create bug report).".format(text, logmod.ERROR_LOG))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._sized:
            self._sized = True
            total = self.splitter.height() or 800
            self.splitter.setSizes([total - 130, 130])

    def closeEvent(self, event):
        if self.task:
            r = QMessageBox.question(self, APP_NAME, "A task is running. Cancel it and quit?")
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            runner.CANCEL.set()
            self.task.wait(15000)
        self.close_project()
        get_logger().removeHandler(self.log_handler)
        event.accept()
