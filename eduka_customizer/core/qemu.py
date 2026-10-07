"""Boot a built ISO in QEMU (BIOS, UEFI or UEFI with Secure Boot)."""

import os
import shutil
import subprocess
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.config import settings
from eduka_customizer.core.log import log

OVMF = {
    "uefi": [("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
             ("/usr/share/OVMF/OVMF_CODE.fd", "/usr/share/OVMF/OVMF_VARS.fd"),
             ("/usr/share/qemu/OVMF.fd", None)],
    "secureboot": [("/usr/share/OVMF/OVMF_CODE_4M.ms.fd", "/usr/share/OVMF/OVMF_VARS_4M.ms.fd"),
                   ("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd", "/usr/share/OVMF/OVMF_VARS_4M.ms.fd"),
                   ("/usr/share/OVMF/OVMF_CODE.secboot.fd", "/usr/share/OVMF/OVMF_VARS.ms.fd")],
}


def kvm_available():
    return os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)


def firmware_files(kind):
    for code, vars_ in OVMF.get(kind, []):
        if Path(code).exists() and (vars_ is None or Path(vars_).exists()):
            return code, vars_
    return None, None


def command(project, iso, firmware="uefi", memory=None, cpus=None, disk=False,
            disk_size=None, kvm=True, display="gtk", audio=False):
    cfg = settings()
    qemu = runner.which("qemu-system-x86_64")
    if not qemu:
        raise RuntimeError("QEMU is not installed (package qemu-system-x86)")
    memory = str(memory or cfg.get("qemu", "memory"))
    cpus = str(cpus or cfg.get("qemu", "cpus"))
    cmd = [qemu, "-name", "Edukasaun OS test", "-m", memory, "-smp", cpus,
           "-machine", "q35" + (",smm=on" if firmware == "secureboot" else ""),
           "-device", "virtio-vga", "-display", display,
           "-device", "qemu-xhci", "-device", "usb-tablet",
           "-nic", "user,model=virtio-net-pci",
           "-drive", "file={},media=cdrom,readonly=on,if=none,id=cd0".format(str(iso).replace(",", ",,")),
           "-device", "ide-cd,drive=cd0,bootindex=0"]
    if audio:
        # Root usually cannot reach the user's sound server; PipeWire/Pulse
        # sockets are passed by the launcher through PULSE_SERVER when possible.
        cmd += ["-audiodev", "pa,id=snd0", "-device", "intel-hda",
                "-device", "hda-duplex,audiodev=snd0"]
    if kvm and kvm_available():
        cmd += ["-enable-kvm", "-cpu", "host"]
    else:
        log.warning("KVM is not available: the virtual machine will be slow")
    if firmware in ("uefi", "secureboot"):
        code, vars_ = firmware_files(firmware)
        if not code:
            raise RuntimeError("OVMF firmware not found (install the 'ovmf' package)")
        if vars_:
            local_vars = project.cache / "qemu-{}-vars.fd".format(firmware)
            if not local_vars.exists():
                shutil.copy2(vars_, local_vars)
            if firmware == "secureboot":
                cmd += ["-global", "driver=cfi.pflash01,property=secure,value=on"]
            cmd += ["-drive", "if=pflash,format=raw,unit=0,readonly=on,file={}".format(code),
                    "-drive", "if=pflash,format=raw,unit=1,file={}".format(local_vars)]
        else:
            cmd += ["-bios", code]
    if disk:
        img = project.cache / "test-disk.qcow2"
        if not img.exists():
            runner.require("qemu-img")
            runner.run(["qemu-img", "create", "-f", "qcow2", img, disk_size or cfg.get("qemu", "disk_size")])
        cmd += ["-drive", "file={},if=virtio,format=qcow2".format(img)]
    return cmd


def start(project, iso=None, **kw):
    iso = iso or project.state.get("last_iso")
    if not iso or not Path(iso).exists():
        raise RuntimeError("No ISO image to test. Build one first.")
    cmd = command(project, iso, **kw)
    log.info("Starting QEMU: %s", " ".join(str(c) for c in cmd))
    log_path = project.logs / "qemu.log"
    fh = open(log_path, "w")
    proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    fh.close()
    return proc


def reset_disk(project):
    img = project.cache / "test-disk.qcow2"
    if img.exists():
        img.unlink()
    for f in project.cache.glob("qemu-*-vars.fd"):
        f.unlink()
