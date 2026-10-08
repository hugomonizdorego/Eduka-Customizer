# Panduan singkat DistroForge 0.17 Alpha

> Panduan lengkap bergambar (PDF): [DistroForge-Panduan.pdf](DistroForge-Panduan.pdf)
> (English: [DistroForge-Guide.pdf](DistroForge-Guide.pdf)). Setelah dipasang:
> `/usr/share/distroforge/guide/` atau tombol *User guide* di halaman **About**.

DistroForge adalah pembangun ISO untuk **semua distribusi berbasis
Debian**: Debian stable, testing, sid dan turunan Debian seperti **LMDE**
, MX Linux, antiX, Kali Linux, Deepin (ISO Ubuntu dan turunannya ditolak).
Sebelum versi 0.17 namanya **Eduka-Customizer**; perintah lama
`eduka-customizer` tetap bekerja. Tidak ada pengaturan bawaan untuk distribusi
tertentu — nama, ID, host name dan homepage kosong sampai Anda mengisinya
(selama kosong, nama dari `os-release` image yang dipakai). **Eduka-Desktop**
tetap tersedia sebagai salah satu desktop. Aplikasinya sendiri bisa dipasang
di Debian, turunan Debian, **Ubuntu dan turunannya**.

## Cara tercepat: Quick Wizard

Buka **Quick Wizard** di sidebar, isi 8 langkah (Sumber → Identitas →
Basis Debian → Desktop → Tampilan → Aplikasi → Branding → Selesai), lalu
tekan **Finish**. Pilih juga *distro untuk apa*, **edisi ISO** dan **edisi
desktop**. Semua jawaban disimpan sebagai recipe `recipe-wizard.json`, ISO
langsung dibangun, dan semua langkah di sidebar terbuka untuk penyesuaian.

## Instalasi

Paket siap pakai untuk dicoba (Debian 13, Ubuntu 24.04 dan turunannya):

```sh
sudo apt install ./release/distroforge_0.17.0~alpha_all.deb
```

Atau build sendiri:

```sh
sudo apt install debhelper python3-pytest dpkg-dev
dpkg-buildpackage -us -uc -b
sudo apt install ../distroforge_0.17.0~alpha_all.deb
distroforge doctor        # cek alat yang dibutuhkan
```

## Baru di 0.17

* **Nama baru: DistroForge.** Paket `distroforge` menggantikan `eduka-customizer`;
  perintah dan pengaturan lama tetap bekerja.
* **Perbaiki otomatis atau manual.** Setiap masalah di *Check & Build* dan *Check the
  installer* punya kolom **How to fix**: *Automatic* diperbaiki dengan tombol **Fix
  automatically** (pasang paket yang kurang, perbaiki database paket, betulkan pengaturan
  Calamares, lalu periksa lagi); *By hand* dibuka dengan klik dua kali. Saat build masih ada
  masalah, muncul pilihan **Fix automatically**, **I will fix it myself** atau **Build anyway**.
* **Peringatan palsu GRUB hilang**: ISO live Debian yang memasang GRUB dari pool ISO saat
  instalasi tidak lagi dilaporkan kekurangan `grub-install`.
* **Review & Apply (langkah 14).** Perubahan tidak langsung diterapkan: semuanya menunggu di
  satu daftar. Centang setiap perubahan yang sudah yakin, atau *Go back and change it*, hapus,
  ubah urutan, lalu **Apply all changes** sekaligus.
* **Target ukuran ISO**: sekecil mungkin, 100 MB, 300 MB, 500 MB, 700 MB (CD), 1 GB, 2 GB,
  4,4 GB (DVD) atau tanpa batas. Kompresi squashfs lossless — ISO yang lebih kecil tidak
  rusak, hanya build lebih lama. Penghemat ukuran yang aman disarankan bila perlu.
* **About**: lisensi (GPL-3.0-or-later), lisensi semua komponen, merek dagang, kredit,
  panduan PDF dan tombol donasi (PayPal, Facebook).
* Semua tulisan di GUI dan `distroforge --help` dirapikan.

## Baru di 0.16

* **System Sounds** (langkah 10) — suara untuk boot, startup (login), logout, shutdown,
  error, peringatan, informasi, notifikasi, e-mail, perangkat USB, kabel daya, baterai
  lemah, dll. Jatuhkan folder: file bernama `boot.ogg`, `login.wav`, `shutdown.ogg`,
  `error.oga`, `notification.ogg` otomatis dicocokkan. Menjadi tema suara default semua
  desktop; suara boot/shutdown lewat layanan systemd, suara login lewat autostart.
* **Welcome Screen** (langkah 11) — 4 halaman yang Anda desain: judul, teks (**tebal**,
  *miring*, [tautan](https://...)), logo, gambar, warna, dan tombol (buka situs, jalankan
  program, mulai installer, tutup). Muncul setelah login sampai pengguna menghapus centang
  *Show this at startup* (atau hanya live / hanya terpasang / hanya dari menu).
* **Identity & Branding** dimuat langsung dari ISO yang diekstrak (nama, ID, versi,
  codename, URL, hostname, label, logo, wallpaper, latar login & GRUB, warna installer).
* **Edisi** dengan istilah resmi tiap desktop: GNOME Core, KDE Plasma dengan KDE Gear,
  Xfce dengan Goodies, MATE extras, ... plus deskripsi paket Debian dari image.
* **Flatpak** untuk semua jenis distro: seluruh katalog Flathub per kategori (Office,
  Audio & Video, Grafis, Internet, Pendidikan, Sains, Game, Developer, Sistem, Utilitas).
* **Replace apps** — *berlaku untuk semuanya* (semua pengguna, semua desktop).
* **Kernel** — terminal untuk memasukkan repositori pihak ke-3 lalu `apt update`; kernelnya
  muncul di daftar. Jika kernel dipasang, repositori ikut tetap di sistem; jika tidak,
  repositori hanya sementara dan dihapus (paling lambat saat build).
* **Look & Feel** — hanya ikon, tema GTK/Qt, tema jendela dan kursor yang cocok dengan
  desktop/WM yang dipilih.
* **Calamares** — slide berisi teks agar orang bisa membaca saat instalasi; ID Calamares
  mengikuti ISO; pemeriksaan installer yang teliti (branding, modul, unpackfs, bootloader,
  display manager, paket, file system, grup, perintah).
* **GRUB Design** (tab di Kernel & Boot) — tema GRUB pihak ke-3 (dicek; ditolak bila tidak
  kompatibel), desain menu GRUB (judul, urutan, default, timeout, warna), dan bootloader
  sistem terpasang: GRUB, GRUB + Secure Boot, systemd-boot, rEFInd. LILO, BURG, EFISTUB dan
  Syslinux dijelaskan alasannya tidak dipakai.
* Tampilan lebih modern: sidebar gradien, tab pil, *Step N of 14* (sejak 0.17: 15 langkah) dengan bar kemajuan.


* **Untuk semua distro berbasis Debian** — default Edukasaun OS dihapus.
  Project lama tetap jalan; file `*-edukasaun*` di image diganti nama otomatis.
* **Build langkah demi langkah** — 12 langkah bernomor. Langkah berikutnya baru
  aktif setelah langkah sebelumnya selesai: tekan **Done — next step** di bawah
  halaman (✔ = selesai). Langkah 1 selesai saat project sudah punya sistem.
  Mode ahli: **Settings → Free navigation** membuka semua menu kapan saja.
* **Menu yang mirip digabung** (tab): *Identity & Branding*; *Software*
  (Packages, Flatpak, Replace apps); *Kernel & Boot*; *Look & Feel* (Themes &
  Icons, Wallpaper & Login, Plymouth); *Advanced* (Terminal & Live, Package
  Workshop).
* **Edisi desktop / WM**: **Mini** (desktop + terminal + file manager, tanpa
  paket rekomendasi), **Compact** (alat inti, jaringan, pengaturan), **Full**
  (desktop lengkap seperti di Debian), **Full with apps** (Full + aplikasi yang
  direkomendasikan: browser, office, mail, media, grafis).
* **Daftar DE, WM dan compositor hanya yang ada di Debian**: GNOME, KDE Plasma,
  Xfce, Cinnamon, MATE, LXQt, LXDE, Budgie, GNOME Flashback, Enlightenment,
  Eduka-Desktop; WM Openbox, i3, Fluxbox, IceWM, awesome, JWM, herbstluftwm,
  bspwm, dwm, spectrwm, Sway, labwc, Wayfire, Hyprland (Debian 13 ke atas).
* **Edisi ISO** di jendela *distro untuk apa?*: **Minimal**, **Full**, **Full
  with recommended apps**.
* **Replace apps** — ganti program bawaan desktop (browser, e-mail, pengolah
  kata, spreadsheet, editor teks, file manager, terminal, penampil gambar,
  pemutar video dan musik, PDF, arsip, kalkulator) dengan program lain. Program
  baru dipasang dan dijadikan default (`/etc/xdg/mimeapps.list` dan
  `update-alternatives`); yang lama bisa dihapus. Desktop tidak ikut terhapus.
* **Check & Build** — pemeriksaan sebelum build: distro, alat build, database
  paket (paket setengah terpasang, `apt-get check`), kernel dan initrd,
  live-boot, sesi desktop dan layar login, installer, identitas, file boot yang
  diedit, mount/`policy-rc.d` tersisa, data pribadi, ruang disk dan perkiraan
  ukuran ISO. Masalah serius menghentikan build; klik dua kali baris untuk
  membuka halaman perbaikannya.

## Alur kerja di GUI (15 langkah)

1. **Start** – buat project (folder kerja), lalu pilih sumber: ISO Debian live
   (disarankan *standard*) atau ISO turunan Debian, *Download Debian* (dicek
   SHA256), *New Debian base* (mmdebstrap), atau *This computer* (snapshot).
   Lalu jawab **distro untuk apa?** (Pendidikan, Server, Profesional, Rumah,
   Lainnya) dan pilih **edisi ISO** — atau tutup untuk membangun sendiri.
2. **Repositories** – stable / testing / sid, repositori sendiri + kuncinya.
3. **Identity & Branding** – tab *Identity* (nama OS, ID, versi, codename,
   URL, nama komputer, label ISO) dan tab *Distro Branding* (paket
   `<id>-branding`, logo, GRUB, Calamares, keyring).
4. **Users** – user live dengan password, tanpa password, atau default Debian;
   akun di dalam image; ubah/hapus password; hapus akun.
5. **Language** – bahasa default, keyboard, zona waktu (default Asia/Dili),
   terjemahan, submenu *Language* di menu boot.
6. **Desktop** – pilih desktop atau WM dan **edisinya** (Mini, Compact, Full,
   Full with apps), layar login, X11/Wayland, compositor, Eduka-Desktop.
7. **Software** – tab *Packages* (semua paket Debian, centang/hapus centang,
   hapus aplikasi bawaan ISO), *Flatpak apps*, *Replace apps*.
8. **Kernel & Boot** – tab *Kernel* (dengan terminal repositori), *Boot Menu* (edit
   grub.cfg/isolinux) dan *GRUB Design* (tema, menu, bootloader).
9. **Look & Feel** – tab *Themes & Icons*, *Wallpaper & Login*, *Plymouth*.
10. **System Sounds** – suara sistem.
11. **Welcome Screen** – layar sambutan 4 halaman.
12. **Installer** – Calamares (slide, pemeriksaan).
13. **Advanced** – tab *Terminal & Live* (desktop image di jendela, terminal
    root, Synaptic) dan *Package Workshop*.
14. **Review & Apply** – daftar semua perubahan yang dipilih di langkah 2–13: centang,
    kembali dan ubah, hapus atau ubah urutan, lalu terapkan sekaligus.
15. **Check & Build** – periksa (perbaiki otomatis), pilih ukuran ISO, build ISO, uji di
    QEMU (BIOS/UEFI/Secure Boot).

Halaman **About** berisi versi, lisensi, lisensi komponen, merek dagang, panduan PDF dan
tombol donasi.

## Baris perintah

```sh
sudo distroforge new ~/mylinux --iso debian-live-13.1.0-amd64-standard.iso
sudo distroforge -p ~/mylinux brand identity name="My Linux" id=mylinux version=1.0
sudo distroforge -p ~/mylinux purpose apply home --edition full_apps
sudo distroforge -p ~/mylinux desktop install xfce --edition compact --dm lightdm
sudo distroforge -p ~/mylinux desktop install eduka            # Eduka-Desktop
sudo distroforge -p ~/mylinux apps replace browser chromium --remove-old
sudo distroforge -p ~/mylinux flatpak install org.kde.gcompris --firstboot
sudo distroforge -p ~/mylinux shell          # terminal di dalam image
sudo distroforge -p ~/mylinux sounds add ~/suara/ && sudo distroforge -p ~/mylinux sounds apply
sudo distroforge -p ~/mylinux welcome apply
sudo distroforge -p ~/mylinux grub-theme add ~/Unduhan/tema-grub.tar.xz --installed
sudo distroforge -p ~/mylinux boot-loader use systemd-boot
sudo distroforge -p ~/mylinux calamares check
sudo distroforge -p ~/mylinux check --deep --fix   # periksa, perbaiki otomatis, periksa lagi
sudo distroforge -p ~/mylinux build --target-size 700   # smallest, 100, 300, 500, ..., none
distroforge -p ~/mylinux test --firmware uefi
distroforge about                            # versi, lisensi, donasi
```

Baris perintah menerapkan setiap perubahan langsung (tanpa daftar Review & Apply).

Build yang bisa diulang (reproducible) memakai *recipe* JSON:
`sudo distroforge -p ~/mylinux recipe apply examples/my-distro.json`
(contoh edisi sekolah dengan Eduka-Desktop: `examples/school-edition.json`).

## Tips

* Jika aplikasi crash dan masih ada mount: `sudo distroforge -p PROJECT clean --unmount-only`.
* Saat Debian rilis versi baru, ubah codename di halaman **Settings**.
* Log lengkap: `PROJECT/logs/distroforge.log`.
* **Log untuk developer** (setiap kali jalan): `/tmp/distroforge/distroforge.log`
  dan `/tmp/distroforge/errors.log` (error + traceback). Menu
  **Settings → Create bug report** membuat arsip untuk dikirim ke developer.
* Screenshot semua halaman: `docs/screenshots/`.

## Lisensi dan dukungan

DistroForge adalah perangkat lunak bebas (GNU GPL versi 3 atau lebih baru), tanpa jaminan.
Debian adalah merek dagang terdaftar Software in the Public Interest, Inc.; DistroForge tidak
berafiliasi dengan Debian — berikan distribusi Anda nama dan logo sendiri.
Dukung proyek ini: [PayPal](https://paypal.me/hugocenturion0311) ·
[Facebook](https://facebook.com/hugomonizdorego).
