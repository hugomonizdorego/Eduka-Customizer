"""Boot a built ISO or SD-card image in QEMU.

PCs: BIOS, UEFI or UEFI with Secure Boot (qemu-system-x86_64 with OVMF).
ARM64: the ISO starts with UEFI (qemu-system-aarch64, machine "virt", EDK2);
an SD-card image starts with its own kernel on the "virt" machine, which tests
the system partition (a Raspberry Pi itself cannot be emulated well enough).
32-bit ARM images start the same way with qemu-system-arm (not the ARMv6 ones).
On an Intel/AMD computer ARM is emulated, so it is slow, but it works.
"""

import os
import shutil
import subprocess
from pathlib import Path

from disco.core import runner
from disco.core.config import settings
from disco.core.log import log

OVMF = {
    "uefi": [("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
             ("/usr/share/OVMF/OVMF_CODE.fd", "/usr/share/OVMF/OVMF_VARS.fd"),
             ("/usr/share/qemu/OVMF.fd", None)],
    "secureboot": [("/usr/share/OVMF/OVMF_CODE_4M.ms.fd", "/usr/share/OVMF/OVMF_VARS_4M.ms.fd"),
                   ("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd", "/usr/share/OVMF/OVMF_VARS_4M.ms.fd"),
                   ("/usr/share/OVMF/OVMF_CODE.secboot.fd", "/usr/share/OVMF/OVMF_VARS.ms.fd")],
}


# EDK2 firmware for ARM machines (packages qemu-efi-aarch64, qemu-efi-arm).
ARM_EFI = {"arm64": ["/usr/share/qemu-efi-aarch64/QEMU_EFI.fd", "/usr/share/AAVMF/AAVMF_CODE.fd"],
           "armhf": ["/usr/share/AAVMF/AAVMF32_CODE.fd", "/usr/share/qemu-efi-arm/QEMU_EFI.fd"]}


def _opt(path):
    """A file name inside a QEMU option list: commas are doubled."""
    return str(path).replace(",", ",,")


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
    cmd = [qemu, "-name", "D!sco test", "-m", memory, "-smp", cpus,
           "-machine", "q35" + (",smm=on" if firmware == "secureboot" else ""),
           "-device", "virtio-vga", "-display", display,
           "-device", "qemu-xhci", "-device", "usb-tablet",
           "-nic", "user,model=virtio-net-pci",
           "-drive", "file={},media=cdrom,readonly=on,if=none,id=cd0".format(_opt(iso)),
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
            cmd += ["-drive", "if=pflash,format=raw,unit=0,readonly=on,file={}".format(_opt(code)),
                    "-drive", "if=pflash,format=raw,unit=1,file={}".format(_opt(local_vars))]
        else:
            cmd += ["-bios", code]
    if disk:
        img = project.cache / "test-disk.qcow2"
        if not img.exists():
            runner.require("qemu-img")
            runner.run(["qemu-img", "create", "-f", "qcow2", img, disk_size or cfg.get("qemu", "disk_size")])
        cmd += ["-drive", "file={},if=virtio,format=qcow2".format(_opt(img))]
    return cmd


def arm_command(project, path, arch, memory=None, cpus=None, display="gtk", **_kw):
    """QEMU for an ARM64/ARM ISO (UEFI) or SD-card image (its own kernel)."""
    cfg = settings()
    binary = "qemu-system-aarch64" if arch == "arm64" else "qemu-system-arm"
    qemu = runner.which(binary)
    if not qemu:
        raise RuntimeError("{} is not installed (package qemu-system-arm)".format(binary))
    memory = str(memory or cfg.get("qemu", "memory"))
    cpus = str(cpus or cfg.get("qemu", "cpus"))
    native = arch == "arm64" and kvm_available() and _host_machine() == "aarch64"
    cpu = "host" if native else ("cortex-a72" if arch == "arm64" else "cortex-a15")
    cmd = [qemu, "-name", "D!sco test ({})".format(arch), "-M", "virt", "-cpu", cpu, "-m", memory, "-smp", cpus,
           "-device", "virtio-gpu-pci", "-display", display, "-device", "qemu-xhci", "-device", "usb-kbd",
           "-device", "usb-tablet", "-nic", "user,model=virtio-net-pci"]
    if native:
        cmd += ["-enable-kvm"]
    else:
        log.warning("ARM is emulated on this computer: the virtual machine is slow")
    path = Path(path)
    if path.suffix == ".iso":
        fw = next((f for f in ARM_EFI.get(arch, []) if Path(f).exists()), None)
        if not fw:
            raise RuntimeError("UEFI firmware for {} QEMU not found (install qemu-efi-aarch64 or qemu-efi-arm)".format(arch))
        cmd += ["-bios", fw, "-device", "virtio-scsi-pci",
                "-drive", "file={},media=cdrom,readonly=on,if=none,id=cd0".format(_opt(path)),
                "-device", "scsi-cd,drive=cd0,bootindex=0"]
        return cmd
    from disco.core import imgbuild
    vmlinuz, initrd = imgbuild.kernel_files(project)
    if not vmlinuz or not vmlinuz.exists():
        raise RuntimeError("No kernel in the project's /boot to start the image with")
    raw = imgbuild.uncompressed(path, project.cache)
    cmd += ["-kernel", str(vmlinuz)] + (["-initrd", str(initrd)] if initrd else [])
    cmd += ["-append", "root=LABEL={} rw rootwait console=ttyAMA0 console=tty1".format(imgbuild.LABEL_ROOT),
            "-drive", "file={},format=raw,if=none,id=hd0".format(_opt(raw)),
            "-device", "virtio-blk-pci,drive=hd0", "-snapshot"]
    return cmd


def _host_machine():
    import platform
    return platform.machine()


def start(project, iso=None, **kw):
    iso = iso or project.state.get("last_iso") or project.state.get("last_image")
    if not iso or not Path(iso).exists():
        raise RuntimeError("No ISO or SD-card image to test. Build one first.")
    arch = project.state.get("distro", {}).get("arch") or "amd64"
    if arch in ("arm64", "armhf"):
        if arch == "armhf" and Path(iso).suffix != ".iso":
            from disco.core import platforms
            if platforms.of_project(project).id == "rpi-armel":
                raise RuntimeError("QEMU cannot start ARMv6 Raspberry Pi images: test this one on the board")
        cmd = arm_command(project, iso, arch, **kw)
    elif arch in ("amd64", "i386"):
        if Path(iso).suffix != ".iso":
            raise RuntimeError("Only ISO images of PCs can be tested here")
        cmd = command(project, iso, **kw)
    else:
        raise RuntimeError("Testing {} images in QEMU is not built in yet: start the ISO on the machine".format(arch))
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
