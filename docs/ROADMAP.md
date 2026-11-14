# Roadmap & rekomendasi

Status: **D!sco 0.11** (November 2026). Nomor versi dimulai lagi dengan nama baru
D!sco (Distro Custom); sebelumnya DistroForge (0.9 Beta) dan Eduka-Customizer (sampai 0.17 Alpha).
Daftar ini adalah usulan langkah berikutnya, diurutkan menurut manfaatnya.

## Selesai di D!sco 0.11
Halaman **Builder** gaya distro builder klasik (preset, daftar paket bercentang, katalog aplikasi,
Prepare → Build base → Install packages → Overlay & scripts → Make image, Build all); **ARM64,
Raspberry Pi (1/Zero sampai 5) dan RISC-V** lewat qemu-user; **image kartu SD** seperti image Debian
(RASPIFIRM + RASPIROOT, raspi-firmware, first boot, sysconf.txt); ISO UEFI ARM64/RISC-V dengan partisi
EFI GPT; rute **live-build**; editor **file sistem** (os-release, lsb-release, issue, hostname, hosts,
motd, /etc/skel, GRUB_BACKGROUND); **Terminal & Browser** (MOTD, PS1, kebijakan Firefox ESR/Chromium);
**dokumen PDF** di desktop; pilihan installer (Calamares, tanpa installer, paket .deb sendiri); 10 langkah;
sekitar 50 perbaikan dari review kode; panduan PDF langkah demi langkah.

## Menuju D!sco 0.12
1. **Uji di perangkat nyata**: Raspberry Pi 3/4/400 dan 5 dengan image dari mirror Debian asli
   (lingkungan pengembangan 0.11 tidak bisa menjangkau deb.debian.org), dan mesin ARM64 UEFI.
2. **Uji live-build penuh** dengan live-build Debian (bukan versi lama Ubuntu).
3. **Kernel Raspberry Pi 5**: pantau dukungan Debian untuk BCM2712 (saat ini eksperimental).
4. **Riwayat preset** (versi) dan impor preset dari URL.
5. **Build tanpa root** (mmdebstrap --mode=unshare) untuk CI.

## Selesai di 0.11 Alpha
Quick Wizard, Distro Branding Studio (paket branding + keyring), Package
Workshop, Themes & Icons, pilihan layar login, X11/Wayland, compositor, log
developer di `/tmp`, dukungan instalasi di Ubuntu, screenshot.

## Selesai di 0.12 Alpha
Menu Language (juga saat membuat ISO), Calamares, Plymouth (pasang, pratinjau,
terapkan, hapus), Boot Menu (edit GRUB/ISOLINUX/EFI dan terapkan dalam
hitungan detik), Kernel (pihak ketiga, hapus, GRUB, firmware), Synaptic di
jendela, paket .deb siap coba di `release/`.

## Selesai di 0.13 Alpha
Menu Users (user live dengan/tanpa password, akun di image), zona waktu
default Asia/Dili, menu bernomor sesuai urutan kerja, perbaikan bug.

## Selesai di 0.14 Alpha
Tujuan distro + rekomendasi, browser paket Debian, hapus aplikasi ISO, drag &
drop tema/ikon/font/wallpaper, galeri wallpaper, compositor asli, LMDE, ikon
menu GPL dan ikon aplikasi flat.

## Selesai di 0.15 Alpha
Pembangun ISO umum untuk semua distro berbasis Debian (tanpa default Edukasaun
OS; Eduka-Desktop tetap ada), 12 langkah bertahap dengan menu digabung (tab),
edisi desktop/WM (Mini, Compact, Full, Full with apps), edisi ISO (Minimal,
Full, Full with recommended apps), daftar DE/WM/compositor khusus Debian,
Replace apps, pemeriksaan sebelum build (Check & Build).

## Selesai di 0.16 Alpha
System Sounds, Welcome Screen (4 halaman), Identity & Branding dari ISO, nama edisi menurut setiap
desktop, katalog Flathub per kategori, Replace apps untuk semua pengguna, terminal repositori kernel
(sementara), Look & Feel per desktop, slide teks dan pemeriksaan Calamares, tema GRUB pihak ke-3,
desain menu GRUB, pilihan bootloader, tampilan modern.

## Selesai di 0.17 Alpha
Nama baru DistroForge, perbaikan otomatis/manual di Check & Build dan pemeriksaan installer,
peringatan palsu `grub-install` dihapus, langkah Review & Apply dengan daftar centang, target
ukuran ISO (100 MB sampai 4,4 GB, kompresi lossless), halaman About (lisensi komponen, merek
dagang, donasi), panduan PDF Indonesia dan Inggris, semua tulisan dirapikan.

## Selesai di 0.9 Beta
Bootloader sistem terpasang (GRUB 2, GRUB Secure Boot, systemd-boot, rEFInd, EFISTUB,
Syslinux/EXTLINUX) dengan pengaturan masing-masing dan langkah installer sendiri yang kompatibel
dengan Calamares; menu digabung menjadi 13 langkah; simpan hanya ISO setelah build; kirim masukan
dengan lampiran; warna baru; perbaikan `runuser`; panduan PDF bahasa Inggris.

## Menuju 1.0

1. **Uji instalasi penuh dengan Calamares** di QEMU untuk setiap bootloader (BIOS dan UEFI,
   ext4/btrfs, dengan dan tanpa enkripsi). Skrip pemasang sudah diuji dengan disk virtual; uji
   end-to-end dengan ISO asli belum.
2. **Aktivasi layanan kirim masukan**: kiriman pertama ke FormSubmit meminta konfirmasi lewat email
   developer satu kali; setelah itu alias acak bisa dipasang di `[feedback] url`.
3. **Terjemahan GUI** (Bahasa Indonesia, Tetun, Português) dengan Qt Linguist.

## Usulan lain

1. **Uji penuh dengan ISO Debian 13 live asli** (LXQt dan standard) di
   perangkat keras nyata, BIOS dan UEFI, termasuk Secure Boot. Unit test dan
   uji boot QEMU sudah ada, tetapi ISO 3 GB nyata belum diuji di lingkungan
   pengembangan ini.
2. **Uji Secure Boot pada hardware nyata** dengan GRUB bernama distro
   (EFI/<id> + salinan EFI/debian) dan Calamares.
3. **Repositori APT untuk Eduka-Desktop** dengan paket menu, tema Plymouth,
   wallpaper dan keyring, sehingga update Eduka-Desktop bisa lewat `apt`.
   D!sco sudah mendukung penambahan repositori dengan kunci.
4. **Folder `debian/` di Eduka-Desktop** (paket sumber yang benar, dengan
   `dpkg-buildpackage`). D!sco sudah mendeteksinya otomatis.
5. **Terjemahan GUI** (Bahasa Indonesia, Tetun, Português) memakai
   Qt Linguist (`pylupdate6`/`lrelease`); teks GUI sudah dirapikan di 0.17
   sehingga siap diterjemahkan.
6. **Ukuran ISO yang tepat**: perkiraan sekarang memakai sampel; build uji
   squashfs cepat (lz4) bisa memberi angka lebih akurat.

## Menuju 0.18 – 0.20

* **Overlay / snapshot rootfs** (overlayfs atau btrfs) sehingga setiap
  perubahan bisa di-*undo*, dan beberapa varian (sekolah, guru, lab) dibuat
  dari satu basis tanpa menyalin seluruh rootfs.
* **Build tanpa root** dengan `unshare`/user namespaces (mmdebstrap
  mendukungnya), lebih aman untuk CI.
* **Terminal tertanam** di GUI (QTermWidget untuk Qt6 bila tersedia di
  Debian) selain terminal eksternal.
* **Repositori APT lokal** yang ditandatangani dengan kunci dari Distro
  Branding (reprepro/aptly), sehingga paket branding bisa di-update online.
* **Pratinjau Plymouth** (`plymouthd --debug` di Xephyr) dan pratinjau menu
  GRUB di dalam aplikasi.
* **Daftar perangkat lunak per profil** (Sekolah Dasar, SMP, SMA, Guru) di
  `desktops.json`/recipe.
* **Profil hardware lama**: kernel `686-pae`, opsi zram, tanpa efek
  grafis – cocok dengan mode *low resource* Eduka-Desktop.
* **Pembaruan ISO inkremental** (hanya membangun ulang squashfs ketika
  rootfs berubah, berdasarkan checksum).
* **Pipeline CI** yang membangun ISO dari recipe pada setiap tag
  dan mengunggahnya sebagai rilis.

## Catatan teknis yang perlu dipantau

* Codename Debian berubah setiap rilis (sekarang: stable `trixie`, testing
  `forky`). Ubah di Settings atau `/etc/disco/disco.conf`.
* Debian tidak membuat ISO live untuk sid: mulai dari testing lalu ganti
  sumber ke sid, atau bootstrap basis sid.
* Jika Debian berhenti memakai ISOLINUX untuk BIOS, mode *replay* tetap
  bekerja karena menyalin konfigurasi boot dari ISO sumber.
