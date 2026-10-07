"""Run external commands with streamed output, progress and cancellation."""

import os
import re
import shlex
import shutil
import signal
import subprocess
import threading

from eduka_customizer.core.log import OUTPUT, log

# Set by the GUI "Cancel" button; checked while commands run.
CANCEL = threading.Event()

_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


class CommandError(RuntimeError):
    def __init__(self, cmd, returncode, tail):
        self.cmd = cmd
        self.returncode = returncode
        self.tail = tail
        text = " ".join(shlex.quote(str(c)) for c in cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        msg = "Command failed ({}): {}".format(returncode, text)
        if tail:
            msg += "\n" + "\n".join(tail[-12:])
        super().__init__(msg)


class Canceled(RuntimeError):
    def __init__(self):
        super().__init__("Operation canceled by user")


Cancelled = Canceled  # old name, kept for scripts written for 0.12 and earlier


def which(program):
    return shutil.which(program, path=os.environ.get("PATH", "") + ":/usr/sbin:/sbin")


def require(*programs):
    """Raise a helpful error when host tools are missing."""
    missing = [p for p in programs if not which(p)]
    if missing:
        raise RuntimeError("Missing host tools: {}. Run 'eduka-customizer doctor' "
                           "to see which Debian packages provide them.".format(", ".join(missing)))


def check_cancel():
    if CANCEL.is_set():
        raise Canceled()


def run(cmd, cwd=None, env=None, input=None, check=True, capture=False,
        quiet=False, progress=None, ok_codes=(0,)):
    """Run *cmd* (a list) and stream its output to the log.

    capture  -- return stdout as text instead of logging it.
    progress -- callable receiving a float percentage parsed from output.
    """
    check_cancel()
    cmd = [str(c) for c in cmd]
    log.debug("$ %s", " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if capture else subprocess.STDOUT,
        start_new_session=True)

    if input is not None:
        def feed():
            try:
                proc.stdin.write(input.encode() if isinstance(input, str) else input)
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        threading.Thread(target=feed, daemon=True).start()

    tail = []
    captured = []
    stderr_lines = []

    if capture:
        def drain_err():
            for raw in proc.stderr:
                stderr_lines.append(raw.decode("utf-8", "replace").rstrip())
        err_thread = threading.Thread(target=drain_err, daemon=True)
        err_thread.start()

    def watchdog():
        while proc.poll() is None:
            if CANCEL.wait(0.3):
                _kill(proc)
                return
    threading.Thread(target=watchdog, daemon=True).start()

    buf = b""
    while True:
        chunk = proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
        if not chunk:
            break
        if capture:
            captured.append(chunk)
            continue
        buf += chunk
        # mksquashfs and friends draw progress bars with carriage returns.
        parts = re.split(rb"[\r\n]", buf)
        buf = parts.pop()
        for raw in parts:
            _emit(raw, tail, quiet, progress)
    if buf and not capture:
        _emit(buf, tail, quiet, progress)

    proc.wait()
    if capture:
        err_thread.join(1)
    if CANCEL.is_set():
        raise Canceled()
    out = b"".join(captured).decode("utf-8", "replace")
    if check and proc.returncode not in ok_codes:
        raise CommandError(cmd, proc.returncode, stderr_lines if capture else tail)
    if capture:
        return out
    return proc.returncode


def _emit(raw, tail, quiet, progress):
    line = raw.decode("utf-8", "replace").rstrip()
    if not line:
        return
    if progress is not None:
        m = _PERCENT.search(line)
        if m:
            try:
                progress(min(100.0, float(m.group(1))))
            except ValueError:
                pass
            # Progress bars are noisy: don't flood the log with them.
            if line.lstrip().startswith("[") or line.count("=") > 8:
                return
    tail.append(line)
    if len(tail) > 200:
        del tail[:100]
    if not quiet:
        log.log(OUTPUT, line)


def _kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def output(cmd, **kw):
    """Run and return stripped stdout."""
    return run(cmd, capture=True, **kw).strip()
