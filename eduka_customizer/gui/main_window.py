"""Main window: sidebar navigation, pages, task status and log console."""

import logging
import time

from eduka_customizer.qt.core import Qt, QTimer
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
        self.setWindowIcon(icon("eduka-customizer", "media-optical", "drive-optical"))
        self.resize(1280, 860)

        self.bridge = LogBridge()
        self.bridge.message.connect(self._append_log)
        self.bridge.crashed.connect(self._show_crash)
        from eduka_customizer.core import log as logmod
        logmod.on_unhandled_error(lambda t, e, tb: self.bridge.crashed.emit("{}: {}".format(t.__name__, e)))
        self.log_handler = QtLogHandler(self.bridge)
        self.log_handler.setLevel(OUTPUT)  # debug details go to /tmp/eduka-customizer
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
        brand = QLabel("Eduka-Customizer")
        brand.setObjectName("brand")
        v.addWidget(brand)
        sub = QLabel("{} · ISO builder for Edukasaun OS".format(VERSION_LABEL))
        sub.setObjectName("brandSub")
        sub.setWordWrap(True)
        v.addWidget(sub)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setIconSize(self.nav.iconSize() * 1.2)
        self.nav.currentRowChanged.connect(self._show_page)
        v.addWidget(self.nav, 1)
        self.theme_btn = QPushButton("Dark mode")
        self.theme_btn.setObjectName("sideButton")
        self.theme_btn.clicked.connect(self.toggle_theme)
        v.addWidget(self.theme_btn)
        return side

    def _header(self):
        h = QFrame()
        h.setObjectName("statusBar")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(28, 10, 20, 10)
        self.project_label = QLabel("No project open")
        f = QFont()
        f.setBold(True)
        self.project_label.setFont(f)
        lay.addWidget(self.project_label)
        self.distro_badge = QLabel("")
        self.distro_badge.setObjectName("badge")
        lay.addWidget(self.distro_badge)
        lay.addStretch(1)
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
        from eduka_customizer.gui.pages import (appearance, branding, build, desktop, flatpak,
                                                identity, packages, project, settings_page, sources,
                                                terminal, themes, wizard, workshop)
        self.pages = []
        for cls in (project.ProjectPage, wizard.WizardPage, identity.IdentityPage,
                    branding.BrandingPage, sources.SourcesPage, packages.PackagesPage,
                    flatpak.FlatpakPage, desktop.DesktopPage, themes.ThemesPage,
                    appearance.AppearancePage, workshop.WorkshopPage, terminal.TerminalPage,
                    build.BuildPage, settings_page.SettingsPage):
            page = cls(self)
            self.pages.append(page)
            self.stack.addWidget(page)
            item = QListWidgetItem(icon(*page.icon_names), page.nav_title if hasattr(page, "nav_title") else page.title)
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)

    def _actions(self):
        quit_ = QAction("Quit", self)
        quit_.setShortcut(QKeySequence.StandardKey.Quit)
        quit_.triggered.connect(self.close)
        self.addAction(quit_)
        for i in range(min(9, len(self.pages))):
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
    def _show_page(self, row):
        if row < 0:
            return
        page = self.pages[row]
        if page.needs_rootfs and not (self.project and self.project.has_rootfs()):
            self.stage_label.setText("Open or create a project with a root filesystem first")
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(self.stack.currentIndex())
            self.nav.blockSignals(False)
            return
        self.stack.setCurrentIndex(row)
        try:
            page.refresh()
        except Exception as e:  # a broken page must not take the window down
            get_logger().error("Could not refresh %s: %s", page.title, e)

    def go(self, page_class_name):
        for i, p in enumerate(self.pages):
            if p.__class__.__name__ == page_class_name:
                self.nav.setCurrentRow(i)

    def update_state(self):
        has = bool(self.project and self.project.has_rootfs())
        for i, page in enumerate(self.pages):
            item = self.nav.item(i)
            enabled = has or not page.needs_rootfs
            flags = item.flags()
            item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags & ~Qt.ItemFlag.ItemIsEnabled)
        if self.project:
            self.project_label.setText("{}  —  {}".format(self.project.state.get("name"), self.project.path))
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
        self._file_handler = add_file_handler(proj.logs / "eduka-customizer.log")
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
            self.stage_label.setText("Cancelling...")

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
