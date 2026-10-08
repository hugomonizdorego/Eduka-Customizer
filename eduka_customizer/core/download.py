"""Download official Debian live images and verify their checksums."""

import hashlib
import os
import re
import urllib.request
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.config import settings
from eduka_customizer.core.log import log

FLAVORS = ["standard", "lxqt", "xfce", "kde", "gnome", "mate", "cinnamon", "lxde"]
UA = {"User-Agent": "DistroForge"}


def base_url(suite):
    cfg = settings()
    if suite == "stable":
        return cfg.get("debian", "live_iso_url").rstrip("/") + "/"
    if suite == "testing":
        return cfg.get("debian", "testing_live_iso_url").rstrip("/") + "/"
    raise ValueError("Debian publishes live images for stable and testing only. For sid, start "
                     "from testing and switch the sources to sid, or bootstrap a new base.")


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def list_images(suite):
    """Return [(filename, sha256)] for the live images of *suite*."""
    url = base_url(suite)
    text = _get(url + "SHA256SUMS").decode()
    images = []
    for line in text.splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+\*?(\S+\.iso)$", line.strip())
        if m:
            images.append((m.group(2), m.group(1)))
    return images


def verify_signature(suite, dest_dir):
    """Check SHA256SUMS.sign against the Debian CD signing keys when available."""
    keyring = "/usr/share/keyrings/debian-role-keys.gpg"
    if not (runner.which("gpgv") and os.path.exists(keyring)):
        log.warning("gpgv or debian-keyring missing: only the SHA256 checksum is verified")
        return None
    url = base_url(suite)
    sums = Path(dest_dir) / "SHA256SUMS"
    sig = Path(dest_dir) / "SHA256SUMS.sign"
    sums.write_bytes(_get(url + "SHA256SUMS"))
    sig.write_bytes(_get(url + "SHA256SUMS.sign"))
    runner.run(["gpgv", "--keyring", keyring, sig, sums])
    log.info("SHA256SUMS signature is valid")
    return True


def download(suite, filename, dest_dir, progress=None):
    images = dict(list_images(suite))
    if filename not in images:
        raise ValueError("{} is not listed in SHA256SUMS".format(filename))
    if "/" in filename or filename.startswith("."):
        raise ValueError("Invalid file name")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    verify_signature(suite, dest_dir)
    target = dest_dir / filename
    part = dest_dir / (filename + ".part")
    expected = images[filename]
    if target.exists() and _sha256(target) == expected:
        log.info("Already downloaded: %s", target)
        return target
    url = base_url(suite) + filename
    done = part.stat().st_size if part.exists() else 0
    headers = dict(UA)
    if done:
        headers["Range"] = "bytes={}-".format(done)
    log.info("Downloading %s", url)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        if done and resp.status != 206:
            done = 0
        total = int(resp.headers.get("Content-Length", "0")) + done
        with open(part, "ab" if done else "wb") as fh:
            while True:
                runner.check_cancel()
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done * 100.0 / total)
    log.info("Verifying checksum")
    if _sha256(part) != expected:
        part.unlink()
        raise RuntimeError("Checksum mismatch: the download is corrupted, please retry")
    os.replace(part, target)
    log.info("Saved %s", target)
    return target


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            runner.check_cancel()
            h.update(chunk)
    return h.hexdigest()
