"""Send a bug report, an error, an idea or a question to the developers.

The report goes over HTTPS to a form-to-e-mail service (FormSubmit) that passes it
on to the developers' mailbox, so nobody needs an e-mail program or an account, and
the address is not shown. What is sent: the text, the files you add and, if you
agree, the logs of DistroForge and the settings of the open project. When there is
no internet the report is kept and sent the next time DistroForge starts.
"""

import base64
import io
import json
import mimetypes
import os
import sys
import tarfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from eduka_customizer import APP_NAME, VERSION_LABEL
from eduka_customizer.core import log as logmod
from eduka_customizer.core.log import log

KINDS = [("bug", "Something does not work (bug)"), ("error", "An error message"),
         ("idea", "An idea or a recommendation"), ("question", "A question"), ("other", "Something else")]
MAX_BYTES = 8 * 1024 * 1024        # all attachments together
LOG_TAIL = 400 * 1024              # the end of each log file
_TO = "aHVnb21vbml6ZG9yZWdvQGdtYWlsLmNvbQ=="


def endpoint():
    """The form address (Settings: [feedback] url can point at an alias)."""
    try:
        from eduka_customizer.core.config import settings
        url = settings().get("feedback", "url")
    except Exception:  # no settings file: the built-in address
        url = ""
    return url or "https://formsubmit.co/" + base64.b64decode(_TO).decode()


def outbox():
    return Path(logmod.DEBUG_DIR) / "outbox"


def system_info():
    from eduka_customizer import qt as qtmod
    from eduka_customizer.core import doctor
    try:
        host = doctor.host_info()["distro"].summary()
    except Exception as e:  # the report must work even when detection fails
        host = "unknown ({})".format(e)
    return "{} {}\nHost: {}\nQt: {}\nPython: {}\n".format(APP_NAME, VERSION_LABEL, host, qtmod.version(),
                                                       sys.version.split()[0])


def _tail(path, limit=LOG_TAIL):
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - limit))
        return fh.read()


def make_report(kind, subject, message, contact="", files=(), include_logs=True, project=None):
    """Write the report (a .tar.gz with report.json, the files and the logs) and return its path."""
    if kind not in dict(KINDS):
        raise ValueError("Unknown kind of report: {}".format(kind))
    if not (subject or "").strip() and not (message or "").strip():
        raise ValueError("Write what happened or what you would like")
    files = [Path(f) for f in files]
    total = sum(f.stat().st_size for f in files if f.is_file())
    if total > MAX_BYTES:
        raise ValueError("The files are too big together ({:.1f} MB, at most {:.0f} MB): leave some out or "
                         "make them smaller".format(total / 1e6, MAX_BYTES / 1e6))
    box = outbox()
    box.mkdir(parents=True, exist_ok=True)
    name = box / (time.strftime("report-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6] + ".tar.gz")
    meta = {"kind": kind, "subject": (subject or "").strip()[:200], "message": (message or "").strip(),
            "contact": (contact or "").strip()[:200], "system": system_info(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S %z"), "files": [f.name for f in files],
            "logs": bool(include_logs)}

    def add_bytes(tf, arcname, data):
        ti = tarfile.TarInfo(arcname)
        ti.size = len(data)
        ti.mtime = int(time.time())
        tf.addfile(ti, io.BytesIO(data))

    with tarfile.open(name, "w:gz") as tf:
        add_bytes(tf, "report.json", json.dumps(meta, indent=2, ensure_ascii=False).encode())
        for f in files:
            if f.is_file():
                tf.add(str(f), arcname="files/" + f.name)
        if include_logs:
            d = Path(logmod.DEBUG_DIR)
            for f in sorted(d.glob("*.log")) if d.is_dir() else []:
                add_bytes(tf, "logs/" + f.name, _tail(f))
            if project is not None:
                for extra in (project.state_file, project.logs / "distroforge.log", project.logs / "qemu.log",
                              project.logs / "live-session.log"):
                    if Path(extra).is_file():
                        add_bytes(tf, "project/" + Path(extra).name, _tail(extra))
    os.chmod(name, 0o600)
    log.info("Report written: %s", name)
    return name


def _multipart(fields, files):
    boundary = "----DistroForge" + uuid.uuid4().hex
    out = io.BytesIO()
    for key, value in fields.items():
        out.write("--{}\r\nContent-Disposition: form-data; name=\"{}\"\r\n\r\n{}\r\n".format(
            boundary, key, value).encode())
    for key, path in files:
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        out.write("--{}\r\nContent-Disposition: form-data; name=\"{}\"; filename=\"{}\"\r\nContent-Type: {}\r\n\r\n"
                  .format(boundary, key, Path(path).name, ctype).encode())
        out.write(Path(path).read_bytes())
        out.write(b"\r\n")
    out.write("--{}--\r\n".format(boundary).encode())
    return out.getvalue(), "multipart/form-data; boundary=" + boundary


def send(report, url=None, timeout=60):
    """Send a report made by make_report. Returns True when the service accepted it."""
    report = Path(report)
    with tarfile.open(report) as tf:
        meta = json.loads(tf.extractfile("report.json").read().decode())
    kinds = dict(KINDS)
    fields = {
        "_subject": "[{} {}] {}: {}".format(APP_NAME, VERSION_LABEL, kinds.get(meta["kind"], meta["kind"]),
                                            meta["subject"] or meta["message"][:60]),
        "_template": "table", "_captcha": "false",
        "Kind": kinds.get(meta["kind"], meta["kind"]),
        "Subject": meta["subject"], "Message": meta["message"] or "-",
        "Contact": meta["contact"] or "(none given)", "System": meta["system"], "Time": meta["time"],
        "Attached": ", ".join(meta["files"]) + (" + logs" if meta["logs"] else "") or "nothing",
    }
    if "@" in meta["contact"]:
        fields["email"] = meta["contact"]  # lets the developers answer
    body, ctype = _multipart(fields, [("attachment", report)])
    req = urllib.request.Request(url or endpoint(), data=body, method="POST",
                                 headers={"Content-Type": ctype, "Accept": "text/html,application/json",
                                          "User-Agent": "{}/{}".format(APP_NAME, VERSION_LABEL),
                                          "Referer": "https://github.com/hugomonizdorego/Eduka-Customizer"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = 200 <= resp.status < 400
    except urllib.error.HTTPError as e:
        log.warning("The report was not accepted: HTTP %s", e.code)
        return False
    except (urllib.error.URLError, OSError) as e:
        log.warning("The report could not be sent: %s", e)
        return False
    if ok:
        sent = outbox() / "sent"
        sent.mkdir(parents=True, exist_ok=True)
        report.replace(sent / report.name)
        log.info("Report sent: %s", report.name)
    return ok


def waiting():
    """Reports that could not be sent yet."""
    box = outbox()
    return sorted(box.glob("report-*.tar.gz")) if box.is_dir() else []


def send_waiting(url=None):
    """Try to send the reports that wait. Returns how many were sent."""
    return sum(1 for r in waiting() if send(r, url=url, timeout=30))
