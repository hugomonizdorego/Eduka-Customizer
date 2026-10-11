"""How much of this computer compressing the ISO may use.

mksquashfs uses every processor core and up to a quarter of the memory by default,
which makes a laptop slow for the whole build. The plan below picks the number of
cores, the memory and the priority from the computer itself and from what the
build is set to (stronger compression for a smaller ISO takes longer, so it gets
more cores in the balanced mode, and keeps the computer usable).
"""

import os

MODES = [("balanced", "Balanced: the computer stays usable (recommended)"),
         ("full", "Full speed: every core, the build finishes first"),
         ("light", "Light: half the cores at low priority, for working while it builds")]
HEAVY = {"xz", "zstd19"}


def machine():
    """{cores, mem_total, mem_available} in bytes."""
    cores = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    total = avail = 0
    try:
        with open("/proc/meminfo") as fh:
            info = {line.split(":")[0]: int(line.split()[1]) * 1024 for line in fh if ":" in line}
        total, avail = info.get("MemTotal", 0), info.get("MemAvailable", info.get("MemFree", 0))
    except (OSError, ValueError, IndexError):
        pass
    return {"cores": max(1, cores), "mem_total": total, "mem_available": avail}


def plan(mode="balanced", compression="zstd", level=15, info=None):
    """{processors, mem_mb, nice, ionice, text} for mksquashfs."""
    info = info or machine()
    cores, avail = info["cores"], info["mem_available"] or info["mem_total"]
    heavy = compression == "xz" or (compression == "zstd" and int(level or 0) >= 19)
    if mode == "full":
        procs, share, nice, ionice = cores, 0.6, 0, None
    elif mode == "light":
        procs, share, nice, ionice = max(1, cores // 2), 0.2, 19, ["-c", "3"]
    else:
        # One core stays free for the desktop; heavy compression may use more of the rest.
        procs = max(1, cores - 1) if heavy or cores <= 4 else max(1, cores - 2)
        share, nice, ionice = 0.4, 10, ["-c", "2", "-n", "7"]
    mem_mb = int(avail * share / 2 ** 20) if avail else 0
    mem_mb = max(256, min(mem_mb, 8192)) if mem_mb else 0
    text = "Uses {} of {} processor cores{}{}.".format(
        procs, cores, " and up to {:.1f} GB of memory".format(mem_mb / 1024) if mem_mb else "",
        "" if nice == 0 else " at {} priority".format("low" if nice >= 19 else "lower"))
    if heavy:
        text += " Strong compression ({}) takes longer: about twice the time of zstd 15.".format(
            "xz" if compression == "xz" else "zstd 19")
    return {"processors": procs, "mem_mb": mem_mb, "nice": nice, "ionice": ionice, "text": text}


def wrap(cmd, p):
    """*cmd* started with the priority of plan *p*."""
    from eduka_customizer.core import runner
    out = list(cmd)
    if p.get("ionice") and runner.which("ionice"):
        out = ["ionice"] + p["ionice"] + out
    if p.get("nice") and runner.which("nice"):
        out = ["nice", "-n", str(p["nice"])] + out
    return out
