#!/usr/bin/env python3
"""Write the PDF user guides docs/DistroForge-Panduan.pdf (Indonesian) and
docs/DistroForge-Guide.pdf (English) from the text below and docs/screenshots.

    QT_QPA_PLATFORM=offscreen python3 tools/make_guide.py
"""

import html
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eduka_customizer import APP_NAME, AUTHOR, DONATE_URL, FACEBOOK_URL, HOMEPAGE, VERSION_LABEL  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"

# Each chapter: (title, [paragraph or ("img", file, caption) or ("list", [items]) or ("code", text)]).
# Text may hold <b>, <i> and <code>; everything else is escaped.

ID = {
    "file": "DistroForge-Panduan.pdf",
    "title": "Panduan Pemakaian",
    "lead": "Membuat distribusi Linux sendiri berbasis Debian sebagai ISO live, langkah demi langkah.",
    "toc": "Isi",
    "note": "Tulisan di aplikasi berbahasa Inggris; panduan ini menyebut nama tombol dan menu persis seperti di layar.",
    "chapters": [
        ("Apa itu {app}?", [
            "{app} adalah perangkat lunak bebas dan sumber terbuka (GPL-3.0-or-later) untuk membuat distribusi "
            "Linux sendiri dari Debian atau turunan Debian. Hasilnya adalah file ISO live yang bisa di-boot dari "
            "USB atau DVD (BIOS dan UEFI) dan bisa dipasang ke komputer dengan installer Calamares.",
            "Sumber yang bisa dipakai:",
            ("list", ["ISO live Debian atau turunan Debian (misalnya LMDE, MX Linux, antiX, Kali Linux, "
                      "Parrot OS, Deepin, SparkyLinux, BunsenLabs, Q4OS)",
                      "sistem dasar Debian baru (stable, testing atau sid) dengan mmdebstrap/debootstrap",
                      "salinan sistem komputer ini (snapshot)"]),
            "ISO berbasis Ubuntu (Ubuntu, Linux Mint edisi Ubuntu, Pop!_OS, elementary OS, Zorin OS) tidak "
            "didukung: {app} khusus untuk distribusi berbasis Debian. {app} sendiri bisa dipasang di Debian, "
            "turunan Debian, dan juga di Ubuntu.",
            "Semua pekerjaan dibagi menjadi 15 langkah. Langkah berikutnya terbuka setelah langkah sebelumnya "
            "selesai, jadi Anda selalu tahu apa yang harus dikerjakan. Pengguna mahir bisa membuka semua langkah "
            "di Settings (Pengaturan).",
        ]),
        ("Memasang dan menjalankan", [
            "Pasang paket .deb (ia menarik semua alat yang dibutuhkan):",
            ("code", "sudo apt install ./distroforge_0.17.0~alpha_all.deb"),
            "Jalankan dari menu aplikasi (<b>DistroForge</b>) atau dari terminal:",
            ("code", "distroforge            # jendela grafis (meminta kata sandi admin)\n"
                     "sudo distroforge --help  # perintah baris"),
            "Perintah lama <code>eduka-customizer</code> tetap bekerja dan membuka {app}. Pengaturan lama dari "
            "/etc/eduka-customizer dibaca otomatis.",
            "Butuh: Debian 12 atau lebih baru (atau turunannya), 4 GB RAM, ruang disk kosong 3 kali ukuran ISO.",
        ]),
        ("Langkah 1 · Start: membuat proyek", [
            "Pilih dari mana distribusi Anda dibuat: buka ISO yang sudah ada, unduh ISO live Debian resmi, buat "
            "sistem dasar Debian baru, atau salin sistem komputer ini. Setiap proyek adalah satu folder yang "
            "menyimpan sistem, pengaturan dan hasil ISO.",
            "Tombol <b>Purpose</b> (tujuan) menanyakan untuk apa distribusi ini (rumah, kantor, sekolah, gaming, server, ...) "
            "dan edisi ISO (minimal, standar, lengkap). Rekomendasinya bisa dipakai atau diabaikan.",
            ("img", "01-start-step-by-step.png", "Langkah 1: membuat atau membuka proyek"),
            "<b>Quick Wizard</b> menanyakan semua hal penting dalam 8 halaman dan menyiapkan semuanya sekaligus.",
            ("img", "00-wizard-step1.png", "Quick Wizard"),
        ]),
        ("Langkah 2 · Repositories", [
            "Pilih versi Debian (stable, testing, sid) dan cermin unduhan, aktifkan contrib/non-free-firmware, "
            "atau tambahkan repositori lain. Paket dan pembaruan diambil dari sini.",
            ("img", "02-repositories.png", "Repositori APT"),
        ]),
        ("Langkah 3 · Identity & Branding", [
            "Beri nama, versi, nama kode, situs web, logo dan wallpaper distribusi Anda. Nilai awal dibaca langsung "
            "dari ISO. {app} membuat paket branding yang mengganti os-release, lsb-release, issue, logo, menu GRUB "
            "dan installer.",
            "<b>Penting:</b> gunakan nama dan logo sendiri. Nama seperti 'Debian ...' atau 'Ubuntu ...' adalah "
            "merek dagang; pemeriksaan sebelum build memberi peringatan bila nama memakainya.",
            ("img", "03b-identity-branding.png", "Identitas & Branding"),
        ]),
        ("Langkah 4 · Users", [
            "Atur pengguna live (bawaan: <code>live</code>, nama lengkap <code>Live</code>), kata sandi atau tanpa "
            "kata sandi, login otomatis, dan akun tambahan di dalam image.",
            ("img", "04-users.png", "Pengguna"),
        ]),
        ("Langkah 5 · Language", [
            "Bahasa bawaan, tata letak keyboard, zona waktu (bawaan Asia/Dili) dan paket bahasa. Bahasa yang "
            "dipilih juga dipakai oleh installer dan menu boot.",
            ("img", "05-language.png", "Bahasa, keyboard dan zona waktu"),
        ]),
        ("Langkah 6 · Desktop", [
            "Pilih desktop (GNOME, KDE Plasma, Xfce, Cinnamon, MATE, LXQt, Budgie, ...) dan edisinya sesuai nama "
            "resmi desktop tersebut (misalnya minimal, standar, lengkap dengan aplikasi). Atur juga layar login "
            "dan sesi bawaan.",
            ("img", "06-desktop-editions.png", "Desktop dan edisinya"),
        ]),
        ("Langkah 7 · Software", [
            "Cari, pasang dan hapus paket Debian; tambahkan aplikasi Flathub per kategori; dan ganti aplikasi "
            "bawaan (peramban, surel, editor, terminal, ...) untuk semua pengguna.",
            ("img", "07-software-packages.png", "Paket"),
            ("img", "07c-software-replace-apps.png", "Mengganti aplikasi bawaan"),
        ]),
        ("Langkah 8 · Kernel & Boot", [
            "Pilih kernel, pasang kernel dari repositori pihak ketiga (repositori sementara dihapus lagi saat "
            "build), ubah menu boot GRUB/ISOLINUX, pilih tema GRUB (diperiksa kecocokannya dulu) dan boot loader "
            "untuk sistem terpasang (GRUB, systemd-boot, rEFInd).",
            ("img", "08-kernel-boot.png", "Kernel"),
            ("img", "08d-grub-design.png", "Desain menu GRUB"),
        ]),
        ("Langkah 9 · Look & Feel", [
            "Tema GTK/Qt, ikon, kursor dan font yang cocok dengan desktop pilihan, wallpaper, layar login dan "
            "animasi boot Plymouth.",
            ("img", "09-look-themes-icons.png", "Tema dan ikon"),
        ]),
        ("Langkah 10 dan 11 · System Sounds & Welcome Screen", [
            "Suara sistem untuk boot, login, logout, mati, kesalahan dan notifikasi. Layar sambutan dengan empat "
            "halaman yang muncul setelah login pertama.",
            ("img", "13-system-sounds.png", "Suara sistem"),
            ("img", "14-welcome-screen.png", "Layar sambutan"),
        ]),
        ("Langkah 12 · Installer", [
            "Atur installer Calamares: modul, urutan, slide, partisi bawaan, dan teks. Tombol "
            "<b>Check the installer</b> menemukan kesalahan sebelum build. Kolom <b>How to fix</b> menunjukkan "
            "apakah masalah bisa diperbaiki otomatis.",
            ("img", "15b-installer-check.png", "Pemeriksaan installer"),
        ]),
        ("Langkah 13 · Advanced", [
            "Terminal di dalam image, sesi live dalam jendela (Xephyr), skrip hook, resep JSON, dan bengkel paket "
            "untuk mengubah file paket Debian yang terpasang.",
            ("img", "16-advanced-terminal-live.png", "Terminal dan sesi live"),
        ]),
        ("Langkah 14 · Review & Apply (tinjau dan terapkan)", [
            "Perubahan dari langkah 2 sampai 13 <b>tidak langsung</b> mengubah image. Semuanya menunggu di daftar "
            "Review & Apply. Tombol hijau di atas menunjukkan berapa perubahan yang menunggu.",
            ("list", ["Centang setiap perubahan yang sudah Anda yakini.",
                      "<b>Go back and change it</b> membuka langkah perubahan itu untuk diubah lagi.",
                      "<b>Remove from the list</b> membatalkan perubahan; <b>Up/Down</b> mengubah urutan.",
                      "<b>Apply all changes</b> baru aktif setelah semua dicentang. Jika satu perubahan "
                      "gagal, yang sudah berhasil keluar dari daftar dan sisanya tetap menunggu."]),
            "Pengguna mahir bisa menerapkan setiap perubahan langsung (Settings → Apply every change at once).",
            ("img", "19-review-apply.png", "Review & Apply"),
        ]),
        ("Langkah 15 · Check & Build (periksa dan build)", [
            "<b>Check now</b> mencari apa saja yang membuat build gagal, ISO tidak bisa boot, atau data "
            "pribadi ikut masuk. Setiap baris menunjukkan cara memperbaikinya:",
            ("list", ["<b>Automatic: ...</b> — tekan <b>Fix automatically</b>, {app} memperbaiki lalu memeriksa "
                      "lagi.",
                      "<b>By hand (double-click)</b> — klik dua kali baris itu untuk membuka langkah yang tepat."]),
            "Saat Anda menekan <b>Build ISO image</b> dan masih ada masalah, {app} bertanya: <b>Fix automatically</b> (perbaiki otomatis), "
            "<b>I will fix it myself</b> (saya perbaiki sendiri) atau <b>Build anyway</b> (tetap build).",
            ("img", "18-check-build.png", "Check & Build"),
        ]),
        ("Ukuran ISO", [
            "Pilih target ukuran: sekecil mungkin, 100 MB, 300 MB, 500 MB, 700 MB (CD), 1 GB, 2 GB, 4,4 GB (DVD) "
            "atau tanpa batas. <b>Estimate</b> mengompres contoh isi sistem dan menghitung ukuran untuk setiap "
            "metode.",
            "Kompresi squashfs bersifat <b>lossless</b>: setiap file kembali persis seperti aslinya. ISO yang "
            "lebih kecil tidak pernah rusak, hanya waktu build lebih lama (xz paling kecil dan paling lambat, "
            "lz4 paling cepat).",
            "Jika target terlalu kecil, {app} menyarankan penghemat ukuran yang aman: dokumentasi, halaman manual, "
            "terjemahan yang tidak dipakai, daftar APT dan kernel lama. File lisensi selalu tetap ada. Yang paling "
            "membantu adalah menghapus aplikasi yang tidak diperlukan.",
            ("img", "18b-build-options.png", "Target ukuran dan opsi build"),
        ]),
        ("Mencoba dan menulis ke USB", [
            "Setelah build, tombol <b>Boot ISO</b> di kartu <b>Test in a virtual machine</b> menjalankan ISO dengan QEMU (BIOS atau UEFI). "
            "ISO bersifat hybrid: tulis ke USB dengan GNOME Disks, balenaEtcher, Ventoy atau:",
            ("code", "sudo dd if=mylinux.iso of=/dev/sdX bs=4M status=progress oflag=sync"),
            "Ganti /dev/sdX dengan perangkat USB yang benar; semua isi USB terhapus.",
        ]),
        ("Perintah baris", [
            "Semua langkah juga tersedia di terminal, sesuai urutan kerja:",
            ("code", "sudo distroforge new --iso debian-live.iso ~/mylinux\n"
                     "cd ~/mylinux\n"
                     "sudo distroforge brand identity name=\"My Linux\" version=1.0\n"
                     "sudo distroforge apt install vlc gimp\n"
                     "sudo distroforge check --fix\n"
                     "sudo distroforge build --target-size 700\n"
                     "sudo distroforge test"),
            "<code>distroforge --help</code> menampilkan semua perintah per langkah; "
            "<code>distroforge PERINTAH --help</code> menjelaskan satu perintah.",
        ]),
        ("Masalah yang sering terjadi", [
            ("list", ["<b>'grub needs /usr/sbin/grub-install in the image'</b> — sejak 0.17 tidak muncul lagi untuk "
                      "ISO live yang memasang GRUB dari pool ISO saat instalasi. Jika muncul, tekan Fix "
                      "automatically (memasang grub-efi/grub-pc-bin).",
                      "<b>Paket setengah terpasang</b> — Fix automatically menjalankan dpkg --configure -a dan "
                      "apt-get -f install.",
                      "<b>Ruang disk kurang</b> — hapus cache dengan <code>sudo distroforge clean</code> atau pindahkan folder "
                      "proyek ke disk lain.",
                      "<b>Tidak ada internet</b> — memasang paket dan Flatpak membutuhkan internet; pengeditan "
                      "lain bekerja tanpa internet.",
                      "<b>Log</b> — semua pesan ada di panel log bawah dan di /tmp/distroforge/distroforge.log."]),
        ]),
        ("Lisensi, merek dagang dan dukungan", [
            "{app} adalah perangkat lunak bebas di bawah GNU General Public License versi 3 atau yang lebih baru, "
            "TANPA JAMINAN APA PUN. Lisensi setiap komponen (Python, Qt, squashfs-tools, xorriso, GRUB, Calamares, "
            "live-boot, Papirus, ...) tercantum di halaman <b>About</b>. Paket di dalam ISO Anda masing-masing "
            "memakai lisensinya sendiri (/usr/share/doc/PAKET/copyright).",
            "Debian adalah merek dagang terdaftar Software in the Public Interest, Inc.; Linux® adalah merek "
            "dagang terdaftar Linus Torvalds. {app} tidak berafiliasi dengan, disponsori atau didukung oleh "
            "Debian. Berikan distribusi Anda nama dan logo sendiri.",
            ("img", "23-about.png", "Halaman About"),
            "Dibuat oleh {author}. Jika {app} membantu Anda, donasi menjaga proyek ini tetap berjalan:",
            ("list", ["PayPal: {donate}", "Facebook: {facebook}", "Proyek: {home}"]),
        ]),
    ],
}

EN = {
    "file": "DistroForge-Guide.pdf",
    "title": "User Guide",
    "lead": "Build your own Debian-based Linux distribution as a live ISO, step by step.",
    "toc": "Contents",
    "chapters": [
        ("What is {app}?", [
            "{app} is free and open source software (GPL-3.0-or-later) to build your own Linux distribution from "
            "Debian or a Debian derivative. The result is a live ISO that boots from a USB stick or DVD (BIOS and "
            "UEFI) and installs with the Calamares installer.",
            "You can start from:",
            ("list", ["a live ISO of Debian or a Debian derivative (for example LMDE, MX Linux, antiX, Kali Linux, "
                      "Parrot OS, Deepin, SparkyLinux, BunsenLabs, Q4OS)",
                      "a new Debian base system (stable, testing or sid) made with mmdebstrap/debootstrap",
                      "a copy of this computer (snapshot)"]),
            "Ubuntu-based ISOs (Ubuntu, Linux Mint's Ubuntu edition, Pop!_OS, elementary OS, Zorin OS) are not "
            "supported: {app} is made for Debian-based distributions. {app} itself installs on Debian, Debian "
            "derivatives and Ubuntu.",
            "The work is split into 15 steps. The next step opens when the one before is done, so you always know "
            "what comes next. Experts can open every step in Settings.",
        ]),
        ("Installing and starting", [
            "Install the .deb package (it pulls in every tool it needs):",
            ("code", "sudo apt install ./distroforge_0.17.0~alpha_all.deb"),
            "Start it from the application menu (<b>DistroForge</b>) or a terminal:",
            ("code", "distroforge            # the window (asks for the admin password)\n"
                     "sudo distroforge --help  # command line"),
            "The old command <code>eduka-customizer</code> still works and opens {app}. Old settings in "
            "/etc/eduka-customizer are read automatically.",
            "Needs: Debian 12 or newer (or a derivative), 4 GB RAM, free disk space of three times the ISO size.",
        ]),
        ("Step 1 · Start: create a project", [
            "Choose where your distribution comes from: open an ISO, download an official Debian live ISO, "
            "bootstrap a new Debian base, or copy this computer. Each project is one folder with the system, the "
            "settings and the built ISO.",
            "<b>Purpose</b> asks what the distribution is for (home, office, school, gaming, server, ...) and the "
            "ISO edition (minimal, standard, full). Use or ignore its recommendations.",
            ("img", "01-start-step-by-step.png", "Step 1: create or open a project"),
            "The <b>Quick Wizard</b> asks everything important on 8 pages and prepares it all at once.",
            ("img", "00-wizard-step1.png", "Quick Wizard"),
        ]),
        ("Step 2 · Repositories", [
            "Choose the Debian version (stable, testing, sid) and mirror, enable contrib/non-free-firmware or add "
            "other repositories. Packages and updates come from here.",
            ("img", "02-repositories.png", "APT repositories"),
        ]),
        ("Step 3 · Identity & Branding", [
            "Give your distribution a name, version, code name, web site, logo and wallpaper. The values start "
            "from what the ISO has. {app} builds a branding package that replaces os-release, lsb-release, issue, "
            "logos, the GRUB menu and the installer branding.",
            "<b>Important:</b> use a name and logo of your own. Names such as 'Debian ...' or 'Ubuntu ...' are "
            "trademarks; the check before building warns when the name uses one.",
            ("img", "03b-identity-branding.png", "Identity & Branding"),
        ]),
        ("Step 4 · Users", [
            "The live user (default <code>live</code>, full name <code>Live</code>), with or without a password, "
            "automatic login, and more accounts in the image.",
            ("img", "04-users.png", "Users"),
        ]),
        ("Step 5 · Language", [
            "Default language, keyboard layout, time zone (default Asia/Dili) and language packs. The language is "
            "also used by the installer and the boot menu.",
            ("img", "05-language.png", "Language, keyboard and time zone"),
        ]),
        ("Step 6 · Desktop", [
            "Choose a desktop (GNOME, KDE Plasma, Xfce, Cinnamon, MATE, LXQt, Budgie, ...) and its edition under "
            "the names the desktop itself uses (minimal, standard, full with applications). Set the login screen "
            "and default session too.",
            ("img", "06-desktop-editions.png", "Desktops and editions"),
        ]),
        ("Step 7 · Software", [
            "Search, install and remove Debian packages; add Flathub applications by category; and replace the "
            "default applications (browser, mail, editor, terminal, ...) for all users.",
            ("img", "07-software-packages.png", "Packages"),
            ("img", "07c-software-replace-apps.png", "Replacing default applications"),
        ]),
        ("Step 8 · Kernel & Boot", [
            "Choose the kernel, install kernels from third-party repositories (temporary repositories are removed "
            "again by the build), edit the GRUB/ISOLINUX boot menu, choose a GRUB theme (checked first) and the "
            "boot loader of installed systems (GRUB, systemd-boot, rEFInd).",
            ("img", "08-kernel-boot.png", "Kernel"),
            ("img", "08d-grub-design.png", "GRUB menu design"),
        ]),
        ("Step 9 · Look & Feel", [
            "GTK/Qt themes, icons, cursors and fonts that fit the chosen desktop, wallpapers, the login screen and "
            "the Plymouth boot splash.",
            ("img", "09-look-themes-icons.png", "Themes and icons"),
        ]),
        ("Steps 10 and 11 · Sounds & Welcome Screen", [
            "System sounds for boot, login, logout, shutdown, errors and notifications. A welcome screen with four "
            "pages shown after the first login.",
            ("img", "13-system-sounds.png", "System sounds"),
            ("img", "14-welcome-screen.png", "Welcome screen"),
        ]),
        ("Step 12 · Installer", [
            "Set up the Calamares installer: modules, order, slides, default partitioning and texts. <b>Check the "
            "installer</b> finds mistakes before the build; the <b>How to fix</b> column says whether a problem is "
            "fixed automatically.",
            ("img", "15b-installer-check.png", "Installer check"),
        ]),
        ("Step 13 · Advanced", [
            "A terminal inside the image, the live session in a window (Xephyr), hook scripts, JSON recipes and "
            "the package workshop to change files of installed Debian packages.",
            ("img", "16-advanced-terminal-live.png", "Terminal and live session"),
        ]),
        ("Step 14 · Review & Apply", [
            "Changes from steps 2 to 13 <b>do not</b> change the image right away. They all wait in the Review & "
            "Apply list. The green button at the top shows how many are waiting.",
            ("list", ["Tick every change you are sure about.",
                      "<b>Go back and change it</b> opens the step of that change.",
                      "<b>Remove from the list</b> drops a change; <b>Up/Down</b> change the order.",
                      "<b>Apply all changes</b> is enabled when everything is ticked. If one change fails, the ones "
                      "applied before it leave the list and the rest keep waiting."]),
            "Experts can apply every change at once (Settings → Apply every change at once).",
            ("img", "19-review-apply.png", "Review & Apply"),
        ]),
        ("Step 15 · Check & Build", [
            "<b>Check now</b> finds what would make the build fail, the ISO not boot, or private data leak into "
            "it. Every row says how to fix it:",
            ("list", ["<b>Automatic: ...</b> — press <b>Fix automatically</b>; {app} fixes it and checks again.",
                      "<b>By hand (double-click)</b> — double-click the row to open the right step."]),
            "When you press <b>Build ISO image</b> with problems left, {app} asks: <b>Fix automatically</b>, <b>I will fix it "
            "myself</b> or <b>Build anyway</b>.",
            ("img", "18-check-build.png", "Check & Build"),
        ]),
        ("ISO size", [
            "Choose a target size: as small as possible, 100 MB, 300 MB, 500 MB, 700 MB (CD), 1 GB, 2 GB, 4.4 GB "
            "(DVD) or no limit. <b>Estimate</b> compresses a sample of the system and computes the size of every "
            "method.",
            "Squashfs compression is <b>lossless</b>: every file comes back exactly as it was. A smaller ISO is "
            "never a damaged ISO, it only takes longer to build (xz is smallest and slowest, lz4 fastest).",
            "When the target is too small, {app} suggests safe size savers: documentation, manual pages, unused "
            "translations, APT lists and old kernels. License files always stay. Removing applications you do "
            "not need helps most.",
            ("img", "18b-build-options.png", "Target size and build options"),
        ]),
        ("Testing and writing to USB", [
            "After the build, <b>Boot ISO</b> in the <b>Test in a virtual machine</b> card boots the ISO with QEMU (BIOS or UEFI). The ISO is "
            "hybrid: write it to a USB stick with GNOME Disks, balenaEtcher, Ventoy or:",
            ("code", "sudo dd if=mylinux.iso of=/dev/sdX bs=4M status=progress oflag=sync"),
            "Replace /dev/sdX with the right USB device; everything on it is erased.",
        ]),
        ("Command line", [
            "Every step is also available in a terminal, in the order of the work:",
            ("code", "sudo distroforge new --iso debian-live.iso ~/mylinux\n"
                     "cd ~/mylinux\n"
                     "sudo distroforge brand identity name=\"My Linux\" version=1.0\n"
                     "sudo distroforge apt install vlc gimp\n"
                     "sudo distroforge check --fix\n"
                     "sudo distroforge build --target-size 700\n"
                     "sudo distroforge test"),
            "<code>distroforge --help</code> lists the commands by step; <code>distroforge COMMAND --help</code> "
            "explains one command.",
        ]),
        ("Common problems", [
            ("list", ["<b>'grub needs /usr/sbin/grub-install in the image'</b> — since 0.17 no longer reported for "
                      "live ISOs that install GRUB from the ISO pool during installation. If it shows, press Fix "
                      "automatically (installs grub-efi/grub-pc-bin).",
                      "<b>Half-installed packages</b> — Fix automatically runs dpkg --configure -a and "
                      "apt-get -f install.",
                      "<b>Not enough disk space</b> — remove caches with <code>sudo distroforge clean</code> or move the project "
                      "folder to another disk.",
                      "<b>No internet</b> — installing packages and Flatpaks needs internet; all other edits work "
                      "offline.",
                      "<b>Log</b> — every message is in the log panel and in /tmp/distroforge/distroforge.log."]),
        ]),
        ("License, trademarks and support", [
            "{app} is free software under the GNU General Public License version 3 or later, WITHOUT ANY WARRANTY. "
            "The license of every component (Python, Qt, squashfs-tools, xorriso, GRUB, Calamares, live-boot, "
            "Papirus, ...) is listed on the <b>About</b> page. The packages in your ISO each keep their own license "
            "(/usr/share/doc/PACKAGE/copyright).",
            "Debian is a registered trademark of Software in the Public Interest, Inc.; Linux® is the registered "
            "trademark of Linus Torvalds. {app} is not affiliated with, sponsored or endorsed by Debian. Give your "
            "distribution a name and logo of its own.",
            ("img", "23-about.png", "The About page"),
            "Made by {author}. If {app} helps you, a donation keeps the project going:",
            ("list", ["PayPal: {donate}", "Facebook: {facebook}", "Project: {home}"]),
        ]),
    ],
}


def fmt(text):
    """Escape everything but the few tags the texts use, then fill in the names."""
    safe = html.escape(text, quote=False)
    for tag in ("b", "i", "code"):
        safe = safe.replace("&lt;{}&gt;".format(tag), "<{}>".format(tag)).replace(
            "&lt;/{}&gt;".format(tag), "</{}>".format(tag))
    return safe.format(app=APP_NAME, author=AUTHOR, donate=DONATE_URL, facebook=FACEBOOK_URL, home=HOMEPAGE)


def img(path, width):
    """<img> with both sizes, so the layout reserves exactly the scaled picture."""
    from eduka_customizer.qt.gui import QImage
    q = QImage(str(path))
    if q.isNull():
        raise SystemExit("missing picture: {}".format(path))
    width = min(width, q.width())
    return "<img src='{}' width='{}' height='{}'>".format(path, width, int(q.height() * width / q.width()))


def to_html(guide, width):
    parts = ["<div align='center' style='line-height: 100%'>",
             "<br>{}<br>".format(img(ROOT / "icons/hicolor/256x256/apps/distroforge.png", 140)),
             "<h1 style='font-size: 34pt'>{}</h1>".format(APP_NAME),
             "<p style='font-size: 18pt'>{} · {}</p>".format(guide["title"], VERSION_LABEL),
             "<p style='font-size: 12pt'>{}</p><br>".format(fmt(guide["lead"])),
             "{}<br><br>".format(img(SHOTS / "19-review-apply.png", width)),
             "<p>{} · GPL-3.0-or-later · {}</p>".format(AUTHOR, HOMEPAGE), "</div>",
             "<h2 style='page-break-before: always'>{}</h2><ol>".format(guide["toc"])]
    if guide.get("note"):
        parts.insert(-1, "<p><i>{}</i></p>".format(fmt(guide["note"])))
    parts += ["<li>{}</li>".format(fmt(t)) for t, _b in guide["chapters"]]
    parts.append("</ol>")
    for n, (title, body) in enumerate(guide["chapters"], 1):
        parts.append("<h2 style='page-break-before: always'>{}. {}</h2>".format(n, fmt(title)))
        for b in body:
            if isinstance(b, str):
                parts.append("<p>{}</p>".format(fmt(b)))
            elif b[0] == "list":
                parts.append("<ul>" + "".join("<li>{}</li>".format(fmt(x)) for x in b[1]) + "</ul>")
            elif b[0] == "code":
                parts.append("<pre style='background-color:#eef3f1'>{}</pre>".format(html.escape(b[1])))
            elif b[0] == "img":
                parts.append("<p align='center' style='line-height: 100%'>{}<br><i>{}</i></p>".format(img(SHOTS / b[1], width), fmt(b[2])))
    return "\n".join(parts)


def write(guide, out):
    from eduka_customizer.qt.core import QMarginsF, QSizeF
    from eduka_customizer.qt.gui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    pdf = QPdfWriter(str(out))
    pdf.setResolution(96)
    pdf.setTitle("{} {}".format(APP_NAME, guide["title"]))
    pdf.setCreator("{} {}".format(APP_NAME, VERSION_LABEL))
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                  QMarginsF(18, 16, 18, 16), QPageLayout.Unit.Millimeter))
    rect = pdf.pageLayout().paintRectPixels(96)
    doc = QTextDocument()
    doc.setDefaultFont(QFont("DejaVu Sans", 10))
    doc.setDefaultStyleSheet("h1, h2 { color: #0f6e56; } h2 { font-size: 17pt; } pre { font-size: 9pt; } "
                             "p, li { line-height: 130%; }")
    doc.setHtml(to_html(guide, rect.width() - 8))
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    doc.print(pdf) if hasattr(doc, "print") else doc.print_(pdf)
    print("wrote", out)


def main():
    from eduka_customizer.qt.gui import QGuiApplication
    app = QGuiApplication(sys.argv)  # noqa: F841 (fonts and images need it)
    for guide in (ID, EN):
        write(guide, ROOT / "docs" / guide["file"])


if __name__ == "__main__":
    main()
