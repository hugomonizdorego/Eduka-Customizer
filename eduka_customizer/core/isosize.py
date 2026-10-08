"""ISO size targets: 100 MB, 300 MB, 500 MB, ... or as small as possible.

The live system is packed into filesystem.squashfs. Squashfs compression is
lossless: every file comes back exactly as it was, so compressing harder never
damages the ISO, it only takes longer to build (and a little longer to start).
For a target size the fastest compression that should reach it is chosen,
from an estimate made by really compressing a sample of the system. When even
the strongest compression is too big, the size savers that remove only files
nobody needs to run the system (documentation, manual pages, unused
translations, APT lists, old kernels) are suggested, with what each saves.
"""

import lzma
import os
from pathlib import Path

from eduka_customizer.core import preflight

MB = 1000 * 1000
TARGETS = [("smallest", "As small as possible (xz, slow)"), ("100", "100 MB"), ("300", "300 MB"),
           ("500", "500 MB"), ("700", "700 MB (fits a CD)"), ("1000", "1 GB"), ("2000", "2 GB"),
           ("4400", "4.4 GB (fits a DVD)"), ("none", "No limit (fastest build)")]
# (compression, level, size compared with xz, build speed) from fastest/largest to slowest/smallest.
METHODS = [("lz4", 0, 1.55, "fastest"), ("zstd", 3, 1.25, "very fast"), ("zstd", 15, 1.11, "fast"),
           ("zstd", 19, 1.06, "slow"), ("xz", 0, 1.0, "slowest")]
SAMPLE_BYTES = 16 * 1024 * 1024


def sample_ratio(rootfs, budget=SAMPLE_BYTES):
    """Compressed/original ratio of an evenly spread sample of the files (xz, like squashfs -comp xz)."""
    files = []
    for root, dirs, names in os.walk(rootfs):
        dirs[:] = [d for d in dirs if not (root == str(rootfs) and d in ("proc", "sys", "dev", "run", "tmp"))]
        for n in names:
            p = os.path.join(root, n)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if os.path.isfile(p) and not os.path.islink(p) and st.st_size > 0:
                files.append((p, st.st_size))
    if not files:
        return 0.38
    total = sum(s for _p, s in files)
    chunk = 1024 * 1024
    # Read about budget/chunk pieces spread evenly over all bytes of the system.
    interval = max(1, total * chunk // budget)
    raw = packed = acc = 0
    mark = 0
    for p, size in files:
        acc += size
        if acc < mark:
            continue
        mark = acc + interval
        try:
            with open(p, "rb") as fh:
                data = fh.read(chunk)
        except OSError:
            continue
        raw += len(data)
        packed += len(lzma.compress(data, preset=6))
    if not raw:
        return 0.38
    # squashfs compresses blocks of 1 MiB with BCJ filters: close to whole-file xz, a little worse.
    return min(1.0, packed / raw * 1.03)


def estimate(project):
    """{system, ratio, other, sizes: {(comp, level): bytes}} for the project."""
    r = project.rootfs
    system = preflight.tree_size(r)
    ratio = sample_ratio(r)
    other = 0
    iso = Path(project.isodir)
    if iso.is_dir():
        for root, _d, names in os.walk(iso):
            for n in names:
                p = os.path.join(root, n)
                if not p.endswith("filesystem.squashfs") and not os.path.islink(p):
                    other += os.path.getsize(p)
    other = max(other, 60 * MB)  # boot loader, kernel and initrd at least
    sizes = {(c, lvl): int(system * ratio * f) + other for c, lvl, f, _s in METHODS}
    return {"system": system, "ratio": ratio, "other": other, "sizes": sizes}


def savers(project):
    """[(cleanup option, text, bytes saved)] of the size savers that would help."""
    from eduka_customizer.core import cleanup
    r = Path(project.rootfs)
    out = []

    def size(*rels):
        return sum(preflight.tree_size(r / x) for x in rels if (r / x).exists())
    out.append(("docs", cleanup.OPTIONS["docs"][0], size("usr/share/doc")))
    out.append(("man_pages", cleanup.OPTIONS["man_pages"][0], size("usr/share/man", "usr/share/info")))
    keep = cleanup.kept_languages(project)
    loc = r / "usr/share/locale"
    drop = [d for d in loc.iterdir() if d.is_dir() and d.name.split("@")[0] not in keep and
            d.name.split("_")[0] not in keep] if loc.is_dir() else []
    out.append(("locales", cleanup.OPTIONS["locales"][0], sum(preflight.tree_size(d) for d in drop)))
    out.append(("apt_lists", cleanup.OPTIONS["apt_lists"][0], size("var/lib/apt/lists")))
    ks = cleanup.kernels(r)
    old = sum(preflight.tree_size(r / "usr/lib/modules" / k) + preflight.tree_size(r / "boot" / ("vmlinuz-" + k))
              for k in ks[:-1])
    out.append(("old_kernels", cleanup.OPTIONS["old_kernels"][0], old))
    return [x for x in out if x[2] > 0]


def plan(est, target):
    """Choose the compression for *target* ('smallest', 'none' or megabytes as text).

    Returns {compression, level, estimate, reachable, speed, target}."""
    if target == "none":
        c, lvl, _f, speed = METHODS[2]  # zstd 15: fast and a good size
    elif target == "smallest":
        c, lvl, _f, speed = METHODS[-1]
    else:
        limit = int(target) * MB
        choice = next((m for m in METHODS if est["sizes"][(m[0], m[1])] <= limit), METHODS[-1])
        c, lvl, _f, speed = choice
    size = est["sizes"][(c, lvl)]
    reachable = target in ("none", "smallest") or size <= int(target) * MB
    return {"compression": c, "level": lvl, "estimate": size, "reachable": reachable, "speed": speed,
            "target": target}


def describe(p, saver_list=()):
    """A sentence for the GUI and the CLI."""
    text = "About {:.0f} MB with {}{} ({} build).".format(
        p["estimate"] / MB, p["compression"], " level {}".format(p["level"]) if p["level"] else "", p["speed"])
    if not p["reachable"]:
        need = p["estimate"] - int(p["target"]) * MB
        text += " {} MB is too small for this system by about {:.0f} MB.".format(p["target"], need / MB)
        useful = [s for s in saver_list if s[2] > 0]
        if useful:
            text += " Size savers: " + "; ".join("{} (about −{:.0f} MB)".format(t.split(": ", 1)[-1],
                                                                              b * 0.4 / MB) for _k, t, b in useful)
        text += ". Removing applications helps most."
    return text
