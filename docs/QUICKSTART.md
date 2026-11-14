# D!sco 0.11.1 quick start

> The full step-by-step guide with pictures: [Disco-Guide.pdf](Disco-Guide.pdf) (the same text:
> [manual.md](manual.md)). After installing: **Welcome → User guide (PDF)** in D!sco.

**D!sco (Distro Custom)** turns a Debian or Devuan live ISO into your own distribution: open the ISO,
change what you like, press **Finish**. It uses Debian's own tools only (live-boot, squashfs, xorriso,
Calamares) and nothing of Ubuntu.

## Before you start

- **Internet connection** (recommended): installing packages, desktops, Flatpak applications and kernels
  needs it. Extracting and editing work offline.
- Debian 12 or newer (or a Debian-based system), 4 GB of memory, about 20 GB of free disk space.
- An ISO to start from: the small **Debian live standard ISO** (no desktop) is the cleanest start.

```sh
sudo apt install ./disco_0.11.1_all.deb
```

Start **D!sco** from the menu (it asks for the administrator password).

## The steps

1. **Welcome** — what D!sco does, recommendations, support. Untick *Show this page when D!sco starts* to
   skip it next time.
2. **Start** — *Customize an ISO*: choose the ISO, type a name, press **Extract and start**. Or *Continue a
   project*: choose it and press **Continue** — D!sco opens the step where you stopped.
3. Go through the steps with **Next** (skip what you do not want to change):
   **System** · **Software** · **Startup** · **Branding** · **Look & Feel** · **Boot** · **Installer** ·
   **Files & Terminal**.
4. **Review & Apply** — your changes wait here; apply them all at once.
5. **Build** — press **Finish: build the image**.

## Easy things

- **Wallpaper and logo**: Branding → Wallpaper & Logo → *Choose...* → keep *Set as default* ticked →
  **Apply**. The same for the login screen, boot menu and picture of new users.
- **What starts by itself**: Startup → tick or untick services and programs → **Apply the ticks**.
- **Applications**: Software → Packages → *Popular applications* → tick → **Install ticked**.
- **Your own files**: Files & Terminal → Files → **Open in my file manager** (no administrator rights
  needed). Put files into `overlay/` the way they should be in the system (`overlay/etc/skel/.bashrc` →
  `/etc/skel/.bashrc`), then **Copy my files into the system**.

## Writing the image

```sh
lsblk     # find the USB stick or SD card first, for example /dev/sdb
sudo dd if=mylinux-1.0-stable-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
xzcat mypi-1.0-stable-arm64.img.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
```

> **WARNING: `dd` erases the whole device named in `of=` without asking.** A wrong letter erases your own
> disk: check it with `lsblk` first.

## Help

- The log: **Show log** at the bottom of the window, or `/tmp/disco/disco.log`.
- **Send feedback** (sidebar) sends a report with screenshots to the developers.
