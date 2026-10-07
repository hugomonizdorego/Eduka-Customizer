"""Look and feel of the Eduka-Customizer window (Eduka green accent)."""

ACCENT = "#00a879"

LIGHT = {
    "bg": "#f4f7f6", "panel": "#ffffff", "side": "#0f2f27", "side_text": "#d7efe7",
    "side_sel": "#00a879", "text": "#1f2d2a", "muted": "#5d6f6a", "border": "#d8e3df",
    "input": "#ffffff", "hover": "#e9f5f1", "log_bg": "#0f1d1a", "log_text": "#cfe9e0",
    "warn": "#b26a00", "error": "#c62828", "ok": "#1b8a5a",
}
DARK = {
    "bg": "#141b19", "panel": "#1c2522", "side": "#0b1512", "side_text": "#cfe9e0",
    "side_sel": "#00a879", "text": "#e3efeb", "muted": "#94a8a2", "border": "#2c3a36",
    "input": "#232e2b", "hover": "#24332f", "log_bg": "#0a100e", "log_text": "#cfe9e0",
    "warn": "#f0a841", "error": "#ff6b6b", "ok": "#4cd394",
}

QSS = """
QWidget {{ color: {text}; font-size: 10pt; }}
QMainWindow, QWidget#pageArea, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {bg}; }}
QFrame#sidebar {{ background: {side}; }}
QLabel#brand {{ color: white; font-size: 13.5pt; font-weight: 700; padding: 18px 12px 2px 18px; }}
QLabel#brandSub {{ color: {side_text}; padding: 0 16px 14px 18px; font-size: 9pt; }}
QListWidget#nav {{ background: transparent; border: none; outline: 0; padding: 4px 8px; }}
QListWidget#nav::item {{ color: {side_text}; padding: 9px 10px; border-radius: 9px; margin: 1px 0; }}
QListWidget#nav::item:hover {{ background: rgba(255,255,255,0.08); }}
QListWidget#nav::item:selected {{ background: {side_sel}; color: white; font-weight: 600; }}
QListWidget#nav::item:disabled {{ color: rgba(215,239,231,0.35); }}
QLabel#pageTitle {{ font-size: 18pt; font-weight: 700; }}
QLabel#pageSubtitle {{ color: {muted}; }}
QLabel#muted {{ color: {muted}; }}
QLabel#badge {{ background: {hover}; border: 1px solid {border}; border-radius: 10px; padding: 3px 10px; }}
QLabel#badgeWarn {{ background: transparent; border: 1px solid {warn}; color: {warn}; border-radius: 10px; padding: 3px 10px; }}
QFrame#card {{ background: {panel}; border: 1px solid {border}; border-radius: 14px; }}
QLabel#cardTitle {{ font-size: 11.5pt; font-weight: 700; }}
QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 9px; padding: 7px 14px; }}
QPushButton:hover {{ background: {hover}; border-color: {accent}; }}
QPushButton:disabled {{ color: {muted}; background: {bg}; }}
QPushButton#primary {{ background: {accent}; color: white; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #00926a; }}
QPushButton#primary:disabled {{ background: {border}; color: {muted}; }}
QPushButton#danger {{ color: {error}; }}
QPushButton#tile {{ text-align: left; padding: 12px; border-radius: 12px; }}
QPushButton#tile:checked {{ border: 2px solid {accent}; background: {hover}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget, QTableWidget {{
    background: {input}; border: 1px solid {border}; border-radius: 8px; padding: 5px; selection-background-color: {accent}; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {accent}; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ min-height: 26px; }}
QPushButton#sideButton {{ background: transparent; color: {side_text}; border: none; padding: 8px 18px; text-align: left; }}
QPushButton#sideButton:hover {{ color: white; background: rgba(255,255,255,0.08); }}
QHeaderView::section {{ background: {bg}; border: none; border-bottom: 1px solid {border}; padding: 5px; font-weight: 600; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; border-bottom: 2px solid transparent; color: {muted}; }}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {accent}; font-weight: 600; }}
QProgressBar {{ border: 1px solid {border}; border-radius: 7px; background: {panel}; text-align: center; height: 14px; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}
QPlainTextEdit#log {{ background: {log_bg}; color: {log_text}; font-family: monospace; font-size: 9pt; border-radius: 10px; }}
QFrame#statusBar {{ background: {panel}; border-top: 1px solid {border}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {accent}; width: 16px; margin: -6px 0; border-radius: 8px; }}
QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; padding: 4px; }}
"""


def stylesheet(dark=False):
    colors = dict(DARK if dark else LIGHT)
    colors["accent"] = ACCENT
    return QSS.format(**colors)


def colors(dark=False):
    return DARK if dark else LIGHT


def palette(dark=False):
    """Qt palette so native widgets (combo boxes, spin boxes) match the theme."""
    from eduka_customizer.qt.gui import QColor, QPalette
    from eduka_customizer.qt.widgets import QStyleFactory
    pal = QStyleFactory.create("Fusion").standardPalette()
    if not dark:
        pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
        return pal
    c = DARK
    roles = {
        QPalette.ColorRole.Window: c["bg"], QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["input"], QPalette.ColorRole.AlternateBase: c["panel"],
        QPalette.ColorRole.Text: c["text"], QPalette.ColorRole.Button: c["panel"],
        QPalette.ColorRole.ButtonText: c["text"], QPalette.ColorRole.ToolTipBase: c["panel"],
        QPalette.ColorRole.ToolTipText: c["text"], QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.PlaceholderText: c["muted"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["muted"]))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c["muted"]))
    return pal
