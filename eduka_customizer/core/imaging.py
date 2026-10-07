"""Image helpers (scale, convert, render logos) built on Qt's QImage.

Works without a display: a QGuiApplication on the "offscreen" platform is
created when none exists. Without Qt the source file is copied unchanged.
"""

import base64
import os
import re
import shutil
from pathlib import Path

_app = None


def _qt():
    global _app
    try:
        from eduka_customizer.qt import gui
    except ImportError:
        return None
    if gui.QGuiApplication.instance() is None and _app is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _app = gui.QGuiApplication(["eduka-customizer"])
    return gui


def image_size(path):
    gui = _qt()
    if not gui:
        return None
    img = gui.QImage(str(path))
    return None if img.isNull() else (img.width(), img.height())


def svg_size(path):
    text = Path(path).read_text(errors="replace")[:4000]
    m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', text)
    if m:
        return int(float(m.group(1))), int(float(m.group(2)))
    w = re.search(r'\swidth="([\d.]+)', text)
    h = re.search(r'\sheight="([\d.]+)', text)
    if w and h:
        return int(float(w.group(1))), int(float(h.group(1)))
    return 256, 256


def load(src):
    """Load PNG/JPEG/SVG into a QImage (SVG rendered at 1024 px)."""
    gui = _qt()
    if not gui:
        return None
    src = str(src)
    if src.lower().endswith(".svg"):
        try:
            from eduka_customizer.qt import svg
        except ImportError:
            return None
        renderer = svg.QSvgRenderer(src)
        if not renderer.isValid():
            return None
        size = renderer.defaultSize()
        scale = 1024 / max(1, max(size.width(), size.height()))
        img = gui.QImage(int(size.width() * scale), int(size.height() * scale),
                         gui.QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = gui.QPainter(img)
        renderer.render(painter)
        painter.end()
        return img
    img = gui.QImage(src)
    return None if img.isNull() else img


def write_png(src, dest, size=None, fit="cover", background=None):
    """Write *src* as PNG. fit: 'cover' crops to size, 'contain' pads."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = load(src)
    if img is None:
        shutil.copy2(src, dest)
        return dest
    from eduka_customizer.qt import core, gui
    if size:
        w, h = size
        mode = (core.Qt.AspectRatioMode.KeepAspectRatioByExpanding if fit == "cover"
                else core.Qt.AspectRatioMode.KeepAspectRatio)
        scaled = img.scaled(w, h, mode, core.Qt.TransformationMode.SmoothTransformation)
        canvas = gui.QImage(w, h, gui.QImage.Format.Format_ARGB32)
        canvas.fill(gui.QColor(background) if background else gui.QColor(0, 0, 0, 0))
        painter = gui.QPainter(canvas)
        painter.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        painter.end()
        img = canvas
    img.save(str(dest), "PNG")
    return dest


def replace_image(logo, target, dest):
    """Render *logo* in the size and format of the existing *target* file."""
    target, dest = Path(target), Path(dest)
    if target.suffix.lower() == ".svg":
        if str(logo).lower().endswith(".svg"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(logo, dest)
            return dest
        w, h = svg_size(target) if target.exists() else (256, 256)
        tmp = dest.with_suffix(".tmp.png")
        write_png(logo, tmp, (w, h), fit="contain")
        data = base64.b64encode(tmp.read_bytes()).decode()
        tmp.unlink()
        dest.write_text('<svg xmlns="http://www.w3.org/2000/svg" '
                        'xmlns:xlink="http://www.w3.org/1999/xlink" width="{0}" height="{1}" '
                        'viewBox="0 0 {0} {1}"><image width="{0}" height="{1}" '
                        'xlink:href="data:image/png;base64,{2}"/></svg>\n'.format(w, h, data))
        return dest
    size = image_size(target) if target.exists() else None
    return write_png(logo, dest, size or (256, 256), fit="contain")
