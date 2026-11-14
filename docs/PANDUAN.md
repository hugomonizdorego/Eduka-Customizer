# Panduan singkat D!sco 0.11 (Distro Custom)

> Panduan lengkap bergambar, langkah demi langkah (PDF, bahasa Inggris): [Disco-Guide.pdf](Disco-Guide.pdf)
> — versi teksnya: [manual.md](manual.md). Setelah dipasang: `/usr/share/disco/guide/` atau tombol
> **Help** di halaman Builder.

**D!sco (Distro Custom)** membangun distribusi Linux Anda sendiri dari **Debian** (stable, testing, sid)
atau **Devuan**, untuk **PC, ARM 64-bit, Raspberry Pi dan RISC-V**. Hanya alat Debian yang dipakai:
`debootstrap`/`mmdebstrap`, `chroot`, `mksquashfs`, `xorriso` dan (bila mau) `live-build`. Tidak ada
bagian Ubuntu (tanpa casper, tanpa PPA, tanpa basis Ubuntu).

Sebelumnya bernama **DistroForge** (0.9 Beta) dan **Eduka-Customizer** (sampai 0.17 Alpha). Nomor versi
dimulai lagi: **0.11 = November**. Perintah lama `distroforge` dan `eduka-customizer` tetap bekerja.

## Instalasi

```sh
sudo apt install ./disco_0.11_all.deb
sudo apt install qemu-user-static binfmt-support    # untuk membangun ARM / Raspberry Pi / RISC-V di PC
sudo apt install live-build                          # opsional: rute live-build
```

Buka **D!sco** dari menu, atau ketik `disco` di terminal (meminta kata sandi administrator).

## Cara tercepat: halaman Builder

1. Buka **1. Builder**, pilih preset (misalnya *Debian Xfce desktop (PC 64-bit)* atau *Raspberry Pi
   desktop (Pi 3, 4, 400)*), tekan **Load**.
2. Isi **Distro name** dan periksa **Build path** (satu folder per distribusi).
3. Centang daftar paket yang dipakai. Klik dua kali sebuah daftar untuk memilih aplikasi dari katalog
   (Internet, Office, Grafis, Audio & Video, Pendidikan, Pemrograman, Sistem, Game, Elektronika & Raspberry
   Pi, Aksesibilitas, Jaringan & Server).
4. Tekan **Prepare**: D!sco memeriksa pilihan dan komputer ini, lalu menyebut alat yang kurang beserta
   perintah untuk memasangnya.
5. Tekan **Build all**: basis sistem dibuat, desktop dan daftar paket dipasang, folder overlay disalin,
   skrip Anda dijalankan, lalu ISO atau image kartu SD dibuat.
6. **Test in QEMU**, lalu tulis ke USB atau kartu SD.

Langkah juga bisa ditekan satu per satu: **Prepare → Build base → Install packages → Overlay & scripts →
Make image**. Setiap langkah boleh diulang.

## Platform

| Platform | Prosesor | Hasil |
|---|---|---|
| PC 64-bit | amd64 | ISO hybrid (BIOS + UEFI) |
| PC lama 32-bit (Debian 12) | i386 | ISO hybrid |
| ARM 64-bit dengan UEFI | arm64 | ISO UEFI |
| Raspberry Pi 3, 4, 400 / Pi 5 (eksperimental) | arm64 | image kartu SD |
| Raspberry Pi 2, 3 (32-bit) | armhf | image kartu SD |
| Raspberry Pi 1, Zero | armel | image kartu SD |
| RISC-V 64 dengan UEFI (eksperimental) | riscv64 | ISO UEFI |

Image Raspberry Pi mengikuti tata letak image resmi Debian: partisi FAT `RASPIFIRM` (firmware, kernel,
config.txt, cmdline.txt) dan partisi ext4 `RASPIROOT` yang membesar ke seluruh kartu saat pertama kali
menyala. File `sysconf.txt` di partisi boot bisa diedit di komputer mana pun sebelum menyala pertama kali
(`hostname=...`, `root_authorized_key=...`).

## Sepuluh langkah di sidebar

1. **Builder** — Builder, Start (dari ISO), Quick Wizard
2. **System** — Repositori, Identitas, File sistem, Pengguna, Bahasa, Init System
3. **Desktop & Apps** — Desktop, Paket, Flatpak, Ganti aplikasi bawaan
4. **Boot** — Kernel, Boot Loader, Menu boot ISO, Raspberry Pi
5. **Branding** — Distro Branding, Wallpaper & Login, Plymouth, Dokumen desktop (PDF)
6. **Look & Feel** — Tema & ikon, Suara sistem, Layar sambutan, Terminal & Browser
7. **Installer** — Calamares, tanpa installer, atau paket .deb sendiri
8. **Advanced** — Terminal & sesi live, Package Workshop
9. **Review & Apply** — semua perubahan menunggu di sini, terapkan sekali
10. **Check & Build** — pemeriksaan, ukuran ISO, kompresi, build

## Yang bisa diedit

* **File identitas sistem** (System → System files): `/etc/os-release` (NAME, VERSION, ID, PRETTY_NAME,
  HOME_URL, LOGO), `/etc/lsb-release`, `/etc/issue` ("Welcome to ..."), `/etc/issue.net`,
  `/etc/hostname`, `/etc/hosts` (127.0.1.1), `/etc/motd`. Tombol *Template from Identity* mengisi otomatis.
* **Bootloader**: latar GRUB untuk sistem terpasang (`GRUB_BACKGROUND`), menu dan splash ISOLINUX
  (640x480) di Boot → Boot Menu.
* **Plymouth**: pasang, pratinjau, atau buat tema dari logo Anda (Branding → Plymouth).
* **/etc/skel**: foto pengguna baru (`.face`), salin folder pengaturan dari komputer ini (misalnya
  `~/.config/xfce4`), wallpaper, tema dan ikon.
* **Layar login LightDM**: background, theme-name, icon-theme-name, default-user-image
  (Branding → Wallpaper & Login).
* **Terminal**: MOTD statis atau dinamis, prompt bash (PS1) di `/etc/bash.bashrc` dan `/etc/skel/.bashrc`.
* **Browser**: kebijakan Firefox ESR (`/etc/firefox-esr/policies/policies.json`: Homepage URL, Locked,
  bookmark) dan Chromium.
* **Dokumen README (PDF)** dengan judul bebas yang menjelaskan sistem operasi Anda, otomatis tersimpan di
  desktop setiap pengguna saat login pertama.

## Menulis ke USB / kartu SD

```sh
lsblk     # cari nama perangkatnya dulu, misalnya /dev/sdb
sudo dd if=mylinux-1.0-stable-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
xzcat mypi-1.0-stable-arm64.img.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
```

> **PERINGATAN: `dd` menghapus seluruh isi perangkat di `of=` tanpa bertanya.** Salah satu huruf saja
> bisa menghapus disk komputer Anda. Periksa dengan `lsblk` dulu.

> **PERINGATAN: jangan hapus folder proyek dengan `rm -rf` saat terminal atau sesi live proyek itu masih
> terbuka** — /dev dan /proc komputer Anda sedang ter-mount di dalamnya. Pakai *Unmount everything* atau
> *Delete the build (keep ISO/IMG)* di Builder.

## Baris perintah

```sh
sudo disco new --preset "Raspberry Pi desktop (Pi 3, 4, 400)" /home/disco/mypi
cd /home/disco/mypi
sudo disco builder --name "My Pi Linux"
sudo disco lists add applications thonny python3-gpiozero
sudo disco build-all
disco platforms     # platform yang didukung
disco presets       # daftar preset
```

## Masalah umum

* **NO_PUBKEY / error tanda tangan APT** — pasang keyring repositori (Debian: `debian-archive-keyring`,
  Devuan: `devuan-keyring`) dan pakai `Signed-By`.
* **Exec format error di chroot** — qemu-user belum terdaftar: `sudo apt install qemu-user-static
  binfmt-support`, lalu tekan **Prepare** lagi.
* **Kernel panic saat boot live** — live-boot atau initramfs hilang: *Install packages*, lalu build ulang
  (Check & Build memperbaikinya otomatis).
* **Log** — semua pesan ada di panel log dan `/tmp/disco/disco.log`. Tombol **Send feedback** mengirim
  laporan beserta screenshot.
