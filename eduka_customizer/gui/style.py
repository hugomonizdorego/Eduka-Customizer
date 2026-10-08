"""Look and feel of the DistroForge window.

Calm slate and blue: a dark slate sidebar, white cards on a cool light grey, and
one blue accent for what you press. Green, amber and red only say how something
went (done, look at it, problem), so the colors keep their meaning. Text keeps
a contrast of at least 4.5:1 (WCAG AA) in both themes.
"""

LIGHT = {
    "bg": "#f3f5f9", "panel": "#ffffff", "side": "#161b26", "side2": "#232c40", "side_text": "#c8d0e0",
    "accent": "#2f6fde", "accent2": "#4c8bf0", "accent_hover": "#2459bf", "accent_rgb": "47,111,222",
    "text": "#1b2232", "muted": "#5a667d", "border": "#dce2ec",
    "input": "#ffffff", "hover": "#edf2fc", "log_bg": "#151a24", "log_text": "#d3dbea",
    "warn": "#b45309", "error": "#c62828", "ok": "#1f8a4c", "soft": "#eef3fd", "shadow": "#d5dbe6",
}
DARK = {
    "bg": "#11151d", "panel": "#1a202b", "side": "#0c1018", "side2": "#1b2336", "side_text": "#c3cbdc",
    "accent": "#4c8bf0", "accent2": "#6aa1f5", "accent_hover": "#3a78e0", "accent_rgb": "76,139,240",
    "text": "#e4e9f2", "muted": "#97a2b8", "border": "#2a3242",
    "input": "#202838", "hover": "#232d40", "log_bg": "#0a0d13", "log_text": "#d3dbea",
    "warn": "#f0a841", "error": "#ff6b6b", "ok": "#4cc68a", "soft": "#1c263b", "shadow": "#0a0d13",
}
ACCENT = LIGHT["accent"]

QSS = """
QWidget {{ color: {text}; font-size: 10pt; font-family: "Inter", "Noto Sans", "Cantarell", "Ubuntu", "DejaVu Sans", sans-serif; }}
QMainWindow, QWidget#pageArea, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {bg}; }}
QFrame#sidebar {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {side2}, stop:0.45 {side}, stop:1 {side}); }}
QFrame#dropZone {{ border: 2px dashed {accent}; border-radius: 14px; background: {soft}; }}
QFrame#dropZone[hover="true"] {{ background: rgba({accent_rgb},0.16); }}
QLabel#brand {{ color: white; font-size: 14.5pt; font-weight: 800; padding: 22px 12px 0 20px; letter-spacing: 0.3px; }}
QLabel#brandSub {{ color: {side_text}; padding: 2px 16px 16px 20px; font-size: 8.8pt; }}
QListWidget#nav {{ background: transparent; border: none; outline: 0; padding: 4px 10px; }}
QListWidget#nav::item {{ color: {side_text}; padding: 7px 10px; border-radius: 10px; margin: 1px 0; }}
QListWidget#nav::item:hover {{ background: rgba(255,255,255,0.07); }}
QListWidget#nav::item:selected {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent2});
    color: white; font-weight: 700; }}
QListWidget#nav::item:disabled {{ color: rgba(200,208,224,0.32); }}
QLabel#pageTitle {{ font-size: 21pt; font-weight: 800; letter-spacing: -0.2px; }}
QLabel#pageSubtitle {{ color: {muted}; font-size: 10.2pt; }}
QLabel#muted {{ color: {muted}; }}
QLabel#badge {{ background: {soft}; border: 1px solid {border}; border-radius: 11px; padding: 4px 12px; color: {text}; }}
QLabel#badgeWarn {{ background: transparent; border: 1px solid {warn}; color: {warn}; border-radius: 11px; padding: 4px 12px; }}
QLabel#stepLabel {{ color: {muted}; font-weight: 600; }}
QFrame#card {{ background: {panel}; border: 1px solid {border}; border-bottom: 2px solid {shadow}; border-radius: 16px; }}
QLabel#cardTitle {{ font-size: 12pt; font-weight: 800; }}
QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 10px; padding: 8px 16px; font-weight: 500; }}
QPushButton:hover {{ background: {hover}; border-color: {accent}; }}
QPushButton:pressed {{ background: {soft}; }}
QPushButton:disabled {{ color: {muted}; background: {bg}; }}
QPushButton#primary {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {accent}, stop:1 {accent2});
    color: white; border: none; font-weight: 700; padding: 9px 18px; }}
QPushButton#primary:hover {{ background: {accent_hover}; }}
QPushButton#primary:disabled {{ background: {border}; color: {muted}; }}
QPushButton#danger {{ color: {error}; }}
QPushButton#danger:hover {{ border-color: {error}; background: rgba(198,40,40,0.08); }}
QPushButton#danger:disabled {{ color: {muted}; }}
QPushButton#tile {{ text-align: left; padding: 14px; border-radius: 14px; }}
QPushButton#tile:checked {{ border: 2px solid {accent}; background: {soft}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget, QTableWidget {{
    background: {input}; border: 1px solid {border}; border-radius: 10px; padding: 6px; selection-background-color: {accent}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {accent}; }}
QListWidget::item, QTreeWidget::item {{ padding: 3px 2px; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ min-height: 28px; }}
QPushButton#sideButton {{ background: transparent; color: {side_text}; border: none; padding: 9px 20px; text-align: left; }}
QPushButton#sideDonate {{ background: rgba(255,255,255,0.08); color: #ffd48a; border: 1px solid rgba(255,212,138,0.35);
    border-radius: 10px; padding: 8px 14px; margin: 4px 14px; text-align: left; font-weight: 700; }}
QPushButton#sideDonate:hover {{ background: rgba(255,212,138,0.15); }}
QPushButton#sideButton:hover {{ color: white; background: rgba(255,255,255,0.07); }}
QHeaderView::section {{ background: {soft}; border: none; border-bottom: 1px solid {border}; padding: 6px; font-weight: 700; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; border-bottom: 2px solid transparent; color: {muted}; }}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {accent}; font-weight: 700; }}
QTabBar::tab:hover {{ color: {text}; }}
QTabWidget#sectionTabs > QTabBar {{ background: {panel}; border-bottom: 1px solid {border}; }}
QTabWidget#sectionTabs > QTabBar::tab {{ padding: 9px 18px; margin: 7px 4px; border: none; border-radius: 15px; }}
QTabWidget#sectionTabs > QTabBar::tab:selected {{ background: {soft}; color: {accent}; border: none; }}
QProgressBar {{ border: none; border-radius: 6px; background: {border}; text-align: center; height: 12px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent2}); border-radius: 6px; }}
QProgressBar#stepProgress {{ max-height: 6px; min-height: 6px; border-radius: 3px; }}
QProgressBar#stepProgress::chunk {{ border-radius: 3px; }}
QPlainTextEdit#log {{ background: {log_bg}; color: {log_text}; font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 9pt; border-radius: 12px; }}
QPlainTextEdit#console {{ background: #0e121a; color: #cfe0ff; font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 9.5pt; border-radius: 12px; border: 1px solid #252d3c; }}
QLineEdit#consoleInput {{ font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; }}
QFrame#statusBar {{ background: {panel}; border-top: 1px solid {border}; }}
QFrame#headerBar {{ background: {panel}; border-bottom: 1px solid {border}; }}
QFrame#stepBar {{ background: {panel}; border-top: 1px solid {border}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 17px; height: 17px; }}
QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {accent}; width: 16px; margin: -6px 0; border-radius: 8px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; padding: 6px; border-radius: 6px; }}
QSplitter::handle {{ background: {bg}; }}
"""


def stylesheet(dark=False):
    return QSS.format(**(DARK if dark else LIGHT))


def colors(dark=False):
    return DARK if dark else LIGHT


def palette(dark=False):
    """Qt palette so native widgets (combo boxes, spin boxes) match the theme."""
    from eduka_customizer.qt.gui import QColor, QPalette
    from eduka_customizer.qt.widgets import QStyleFactory
    pal = QStyleFactory.create("Fusion").standardPalette()
    if not dark:
        pal.setColor(QPalette.ColorRole.Highlight, QColor(LIGHT["accent"]))
        return pal
    c = DARK
    roles = {
        QPalette.ColorRole.Window: c["bg"], QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["input"], QPalette.ColorRole.AlternateBase: c["panel"],
        QPalette.ColorRole.Text: c["text"], QPalette.ColorRole.Button: c["panel"],
        QPalette.ColorRole.ButtonText: c["text"], QPalette.ColorRole.ToolTipBase: c["panel"],
        QPalette.ColorRole.ToolTipText: c["text"], QPalette.ColorRole.Highlight: c["accent"],
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.PlaceholderText: c["muted"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["muted"]))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c["muted"]))
    return pal
