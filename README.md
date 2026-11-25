# VOMANTIS

Aplikasi web maintenance mesin berbasis **Django**, menggunakan **MariaDB** sebagai database utama. Antarmuka berbahasa Indonesia memakai CSS, font, dan ikon **Corona Admin** dari direktori `template_styles`. Tidak perlu menjalankan npm atau mengompilasi template.

**Panduan pengguna:** [Panduan Penggunaan VOMANTIS](docs/PANDUAN_PENGGUNAAN.md) — langkah setiap fitur, hak akses, contoh penggunaan, serta screenshot fitur dan langkah penggunaan.

## 1. Menjalankan aplikasi lokal

Konfigurasi default sekarang memakai MariaDB. Siapkan database dan environment pada bagian 2 sebelum menjalankan aplikasi. Jika workspace masih memiliki `db.sqlite3`, data tersebut tidak otomatis dipindahkan. Ikuti [panduan migrasi SQLite dan setup Debian](DEPLOYMENT.md).

**Server Debian kosong:** unggah proyek, lalu jalankan `sudo bash scripts/setup-debian.sh --host maintenance.example.com --email admin@example.com`. Untuk LAN dengan IP: `sudo bash scripts/setup-debian.sh --host 192.168.1.10 --http`. Setup menjalankan `seed_admin` dan meminta password untuk akun `admin`. Panduan lengkap: [DEPLOYMENT.md](DEPLOYMENT.md).

Dari PowerShell di `D:\VOMANTIS`:

```powershell
.\start.ps1
```

Buka **http://127.0.0.1:8000/**.

`start.ps1` menjalankan migrasi, menyiapkan grup peran, membuat jadwal bulan berjalan untuk mesin yang sudah Anda tambahkan, lalu menjalankan server dan penjadwal latar belakang. Penjadwal memeriksa bulan berjalan setiap jam. Proses penjadwal dihentikan saat script/server dihentikan. Hasilnya tercatat di `scheduler.log` dan `scheduler-error.log`.

Jika kebijakan PowerShell menghalangi script, jalankan dua terminal:

```powershell
# Terminal 1: aplikasi
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

```powershell
# Terminal 2: penjadwal otomatis
.\.venv\Scripts\python.exe manage.py run_scheduler
```

Seeder hanya membuat akun administrator. Jalankan `seed_admin` untuk membuat username `admin` dengan password yang Anda isi sendiri; pemanggilan ulang tidak mengubah akun yang sudah ada. Tambahkan akun operasional melalui Django Admin.

## 2. Instalasi dari awal

Prasyarat: Python **3.11–3.14**, pip, dan **MariaDB 10.11+**. Skrip setup menargetkan Debian 12/13. Implementasi ini diuji dengan Python 3.14 dan Django 5.2.19. Kompatibilitas Python mengikuti [catatan rilis Django 5.2](https://docs.djangoproject.com/en/5.2/releases/5.2/).

### Database MariaDB

Buat database dan user dengan akun administrator MariaDB (ganti password contoh):

```sql
CREATE DATABASE vomantis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vomantis'@'127.0.0.1' IDENTIFIED BY 'GANTI_PASSWORD_DB';
GRANT ALL PRIVILEGES ON vomantis.* TO 'vomantis'@'127.0.0.1';
```

MariaDB memakai backend `django.db.backends.mysql` dan driver `mysqlclient`. Pada Linux, pasang `python3-dev default-libmysqlclient-dev build-essential pkg-config` sebelum pip. Muat tabel timezone MariaDB untuk agregasi tanggal/timezone Django; skrip Debian melakukannya otomatis. Untuk instalasi manual Linux: `sudo mariadb-tzinfo-to-sql /usr/share/zoneinfo | sudo mariadb mysql`. Pada Windows, gunakan paket tabel timezone resmi MariaDB.

Set environment di setiap terminal aplikasi dan scheduler. File [.env.example](.env.example) hanya referensi; `.env` tidak dibaca otomatis.

```powershell
$env:DB_NAME = 'vomantis'
$env:DB_USER = 'vomantis'
$env:DB_PASSWORD = 'GANTI_PASSWORD_DB'
$env:DB_HOST = '127.0.0.1'
```

```bash
export DB_NAME=vomantis DB_USER=vomantis DB_HOST=127.0.0.1
export DB_PASSWORD='GANTI_PASSWORD_DB'
```

### Windows / PowerShell

```powershell
cd D:\VOMANTIS
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py create_roles
.\.venv\Scripts\python.exe manage.py seed_admin
```

Jika alias `py` / `python` tidak dapat diakses, gunakan lokasi executable Python yang sesungguhnya. Contoh yang digunakan di komputer ini:

```powershell
& 'C:\Users\s14ki\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m venv .venv
```

Sesudah virtual environment tersedia, gunakan `.\.venv\Scripts\python.exe` sehingga aktivasi virtual environment tidak diperlukan.

### Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py create_roles
.venv/bin/python manage.py seed_admin
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Jalankan `.venv/bin/python manage.py run_scheduler` di terminal kedua untuk mengaktifkan jadwal otomatis selama pengembangan.

`requirements-lock.txt` menyimpan versi yang dipakai saat pengujian. `requirements.txt` menyediakan rentang versi jika ingin memperbarui dependensi secara sengaja.

Instalasi bersih membuat skema database, grup Manager/Teknisi, dan satu akun admin melalui `seed_admin`. Tidak ada akun demo, mesin, tiket, laporan, atau lampiran contoh. SQL lama hanya dapat diimpor secara manual bila memang diperlukan.

## 3. Pengaturan akun

1. Masuk ke VOMANTIS sebagai Manager atau superuser yang dibuat dengan `seed_admin`.
2. Buka **Akun tim → Tambah akun**. Isi nama lengkap, username, peran **Manager** atau **Teknisi**, dan password awal.
3. Akun Manager dapat meninjau tiket dan laporan. Akun Teknisi aktif langsung tersedia di pilihan penugasan.
4. Pengguna masuk melalui `/login/`. Password dapat diganti dari menu **Ubah password**. Pengaturan akun juga tersedia bagi superuser melalui Django Admin.

Superuser diperlakukan sebagai Manager pada aplikasi. Teknisi hanya dapat melihat tiket yang ditugaskan kepadanya, termasuk lampiran tiket tersebut. Informasi master mesin tersedia bagi semua pengguna yang sudah login.

## 4. Alur penggunaan

### Manager

1. **Master mesin → Tambah mesin.** Isi kode lama, nama, serial bila tersedia, kategori, lokasi, kondisi, foto, dan tanggal acuan maintenance.
2. Setiap mesin mendapat `asset_uid` unik yang tidak dapat diedit. Kode aset lama boleh berulang karena tetap diperlukan untuk pelacakan data lama. Serial yang diisi harus unik.
3. Buka detail mesin untuk informasi, riwayat, dan unduhan QR. Di **Galeri mesin**, gunakan **Hapus foto** pada foto yang dipilih. **Nonaktifkan / Afkir** mengubah status mesin. **Hapus aset** mengeluarkan aset dari Master mesin dan penjadwalan baru sambil mempertahankan riwayatnya.
4. Buka **Jadwal maintenance**, pilih bulan, lalu buat jadwal bulanan; atau buat **Work order** korektif secara manual.
5. Buka tiket → **Atur penugasan**. Tentukan teknisi, tanggal, prioritas, tingkat kerusakan, dan centang **Setujui jadwal dan penugasan**. Gunakan **Tolak work order** dengan alasan untuk menolak tiket yang belum disetujui.
6. Ikuti progres pada kanban atau daftar tiket. Indikator lonceng menampilkan jumlah laporan berstatus **Review**; notifikasi bersifat di dalam aplikasi.
7. Buka laporan, periksa setiap kartu dan lampiran, lalu setujui atau kembalikan dengan catatan revisi. **Jejak aktivitas** menampilkan nama Manager yang mengambil keputusan dan waktu keputusan.

### Teknisi

1. Masuk menggunakan akun teknisi dan buka **Work order saya**.
2. Buka tiket terkonfirmasi → **Mulai pekerjaan**.
3. Pilih **Isi laporan maintenance**. Isi kondisi sebelum, kondisi setelah, dan hasil pemeriksaan mesin.
4. Unggah bukti sebelum/sesudah. Tambahkan kartu untuk setiap komponen atau titik kerusakan, lengkap dengan temuan, tindakan, bukti kerusakan, dan bukti perbaikan.
5. Kirim laporan untuk review. Jika dikembalikan, baca catatan Manager dan perbaiki laporan. Tandai **Hapus foto** pada foto yang akan dikeluarkan saat revisi dikirim. Unggah pengganti jika foto itu satu-satunya bukti untuk tahap tersebut.

Format lampiran: JPG, JPEG, PNG, WebP, MP4, atau WebM. Maksimal **25 MB per berkas** dan **20 kartu** per laporan. Foto diverifikasi dengan Pillow, video diperiksa ekstensi dan signature container. Lampiran hanya dapat dibuka setelah login dan pemeriksaan hak akses. Foto yang dikeluarkan dari laporan disimpan sebagai arsip audit. Setiap pengiriman laporan menyimpan snapshot isi kartu dan daftar lampiran dalam jejak aktivitas.

## 5. Penjadwalan bulanan otomatis

Tanggal mengikuti `maintenance_anchor` setiap mesin. Misalnya acuan tanggal 31 menghasilkan 28 Februari pada tahun biasa, lalu kembali ke 31 Maret. Mesin berstatus **Afkir** tidak mendapat jadwal baru.

Satu mesin mendapat maksimal satu tiket otomatis per bulan; kunci unik database mencegah duplikasi saat penjadwal dijalankan ulang. Tiket otomatis berstatus **Open** dan belum dikonfirmasi. Manager tetap menentukan teknisi serta menyetujui jadwal.

Untuk MVP, satu teknisi mendapat maksimal **satu tiket aktif terkonfirmasi per hari**, sehingga tanggal tugas tidak tumpang tindih. Gunakan tanggal lain atau teknisi lain ketika terjadi benturan. Jam kerja, shift, dan kalender produksi belum dimodelkan.

```powershell
# Membuat jadwal bulan berjalan satu kali
.\.venv\Scripts\python.exe manage.py generate_schedules

# Membuat jadwal bulan tertentu; aman diulang
.\.venv\Scripts\python.exe manage.py generate_schedules --month 2026-12

# Penjadwal jangka panjang
.\.venv\Scripts\python.exe manage.py run_scheduler

# Satu siklus untuk pemeriksaan
.\.venv\Scripts\python.exe manage.py run_scheduler --once
```

Alternatif Windows Task Scheduler, buat task harian dengan:

- **Program:** `D:\VOMANTIS\.venv\Scripts\python.exe`
- **Arguments:** `manage.py generate_schedules`
- **Start in:** `D:\VOMANTIS`
- **Trigger:** setiap hari pukul 07.00 waktu lokal Jakarta.

Alternatif cron untuk server yang timezone-nya sudah disetel ke Asia/Jakarta:

```cron
0 7 * * * cd /path/to/VOMANTIS && /path/to/VOMANTIS/.venv/bin/python manage.py generate_schedules >> scheduler.log 2>&1
```

Pilih salah satu penjadwal. Pada pengembangan lokal tidak ada service OS yang didaftarkan. Skrip Debian mendaftarkan systemd timer setiap jam; jangan menjalankan scheduler kedua. Jika aplikasi mati melewati pergantian bulan, bulan berjalan diproses saat penjadwal kembali hidup. Bulan yang terlewat dapat dibuat secara eksplisit dengan `--month`.

## 6. Impor data SQL lama (opsional)

Instalasi fresh tidak mengimpor SQL lama. Fitur impor tetap tersedia secara manual bila diperlukan. `Main_data.sql` asli **tidak diubah**. File yang diberikan berisi **14 tabel dan 5 baris data**, seluruh baris berada pada `rumus_indikator`; tabel mesin dan transaksi pada sumber masih kosong.

- Semua tabel dan kolom sumber dipetakan ke MariaDB dengan nama tabel/kolom asal.
- Relasi mesin, work order, kondisi awal, kerusakan, PM, downtime, serta KPI tetap tersedia.
- Kolom turunan KPI dan SUS memakai generated columns MariaDB.
- Byte asli SQL, SHA-256, ringkasan tabel, serta snapshot tiap baris impor disimpan dalam database.
- Impor berulang terhadap file yang sama tidak menambah duplikat. Konflik primary key dengan isi berbeda membatalkan seluruh impor, tanpa menimpa data.
- Parser membaca `CREATE TABLE` dan literal `INSERT ... VALUES`; SQL sumber tidak dieksekusi langsung. Pernyataan tidak didukung ditolak agar data tidak terlewat diam-diam.
- Penghapusan aset dari Master mesin menyimpan baris aset untuk kebutuhan riwayat dan verifikasi arsip. Relasi historis dilindungi dengan `PROTECT`.

```powershell
.\.venv\Scripts\python.exe manage.py import_main_data
.\.venv\Scripts\python.exe manage.py verify_source_data
```

Verifikasi mencocokkan checksum, semua kolom skema, snapshot asli, serta keberadaan objek hasil impor. Perubahan data operasional yang disengaja tidak mengganti snapshot sumber. Melalui **Data & arsip**, Manager dapat membaca seluruh tabel, menambah data pendukung, mengunduh CSV, serta mengunduh SQL asli.

Rincian pemetaan: [docs/DATA_MAPPING.md](docs/DATA_MAPPING.md).

## 7. Pengujian dan pemeriksaan

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test maintenance
```

Untuk MariaDB, gunakan user pengujian yang juga memiliki hak pada `test_vomantis.*`; jangan jalankan tes menggunakan database produksi. Tes menggunakan database terpisah dan direktori lampiran sementara; database kerja tidak dihapus atau diubah oleh tes. Cakupan meliputi preservasi SQL, ID unik dengan kode lama berulang, batas akses per peran, akses lampiran, CSRF, alur laporan/revisi/approval, penonaktifan mesin, penjadwalan akhir bulan dan duplikasi, benturan teknisi, rumus KPI/SUS, serta rendering halaman utama.

Pemeriksaan browser opsional tersedia di `scripts/browser_check.py`. Gunakan akun Manager/superuser milik Anda melalui environment `VOMANTIS_TEST_USERNAME` dan `VOMANTIS_TEST_PASSWORD`; tidak ada kredensial bawaan atau kebutuhan data contoh. Pasang Playwright dan jalankan script dengan server lokal aktif. Pemeriksaan mencakup halaman kosong, navigasi desktop/mobile, dan form wajib isi. Microsoft Edge diperlukan; Playwright bukan dependensi runtime aplikasi.

## 8. Akses dari HP di jaringan lokal

Untuk pengujian melalui HP yang terhubung Wi-Fi yang sama, sesuaikan alamat LAN komputer:

```powershell
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,192.168.1.10'
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

Buka `http://192.168.1.10:8000/` di HP. Sesuaikan izin firewall Windows untuk port tersebut pada jaringan privat. QR memuat alamat host yang dipakai saat mengunduhnya: buka halaman mesin melalui alamat LAN sebelum mengunduh QR untuk HP. QR dengan `127.0.0.1` hanya cocok untuk komputer yang sama.

## 9. Backup dan konfigurasi

Simpan **dump MariaDB dan seluruh direktori media sebagai satu backup**. Hentikan penulisan aplikasi dan penjadwal selama backup database/media. File sumber `Main_data.sql`, kode aplikasi, dan konfigurasi rahasia juga perlu disimpan secara privat. Perintah backup server tersedia di [DEPLOYMENT.md](DEPLOYMENT.md#5-backup).

Konfigurasi melalui environment variables, tanpa pembaca `.env` otomatis:

| Variabel | Default pengembangan | Fungsi |
| --- | --- | --- |
| `DB_ENGINE` | `mariadb` | `sqlite` hanya untuk ekspor data lama atau tes eksplisit |
| `DB_NAME` / `DB_USER` | `vomantis` | Nama database / akun MariaDB |
| `DB_PASSWORD` | Kosong | Isi sesuai password user MariaDB |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` | Alamat MariaDB |
| `SQLITE_PATH` | `db.sqlite3` proyek | Berlaku hanya jika DB_ENGINE=sqlite |
| `DJANGO_STATIC_ROOT` / `DJANGO_MEDIA_ROOT` | `staticfiles/` / `media/` proyek | Lokasi static hasil collectstatic dan unggahan |
| `DJANGO_COOKIE_SECURE` | `0` saat debug, `1` saat production | Cookie HTTPS; `0` hanya untuk HTTP LAN |
| `DJANGO_SECURE_SSL_REDIRECT` | `0` | Redirect HTTPS; skrip HTTPS mengatur `1` |
| `DJANGO_TRUST_PROXY` | `0` | Percayai header HTTPS hanya dari reverse proxy terkontrol |
| `DJANGO_DEBUG` | `1` | Gunakan `0` untuk deployment |
| `DJANGO_SECRET_KEY` | Kunci lokal development | Wajib diatur sendiri jika DEBUG=0 |
| `DJANGO_ALLOWED_HOSTS` | localhost, 127.0.0.1, [::1], testserver | Daftar host dipisahkan koma |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Kosong | Origin HTTPS yang dipercaya bila diperlukan |

Server `runserver` ditujukan untuk pengembangan. Deployment memerlukan server WSGI, HTTPS, `DEBUG=0`, secret key sendiri, konfigurasi static setelah `collectstatic`, dan penjadwal yang dikelola service/Task Scheduler. Jangan mempublikasikan direktori `media` langsung karena bukti disajikan lewat view yang memeriksa akses. Gunakan skrip setup dan [panduan Debian](DEPLOYMENT.md) untuk deployment server.

MariaDB menggunakan InnoDB, charset utf8mb4, strict mode, dan isolasi read committed. Constraint benturan teknisi menggunakan generated column agar tetap ditegakkan pada MariaDB. Fitur AI dan penjadwalan berdasarkan jam operasional merupakan pengembangan lanjutan sesuai PRD.

## 10. Struktur proyek

```text
VOMANTIS/
  manage.py                  # Entry point Django
  start.ps1                  # Server + penjadwal lokal Windows
  scripts/setup-debian.sh     # Instalasi MariaDB + aplikasi server Debian
  DEPLOYMENT.md              # Setup, transfer data lama, dan backup
  requirements*.txt          # Dependensi
  vomantis/                  # Settings, URL, WSGI
  maintenance/
    models.py                # Semua tabel sumber + alur operasional
    views.py, forms.py       # Halaman, hak akses, validasi
    services.py              # Penjadwal dan transisi tiket
    source_import.py         # Parser, arsip, verifikasi SQL
    management/commands/     # Impor opsional, verifikasi, peran, scheduler
    migrations/              # Migrasi skema database
    tests.py                 # Pengujian otomatis
  templates/                 # Template Django
  static/                    # CSS dan JavaScript aplikasi
  template_styles/           # Corona Admin asli, tetap dipertahankan
  docs/                      # Pemetaan data dan arsitektur
  Main_data.sql              # Sumber SQL asli
  PRD.md                     # Kebutuhan produk asli
  db.sqlite3                 # Database SQLite lama (opsional), tidak dilacak Git
  media/                     # Foto dan bukti, tidak dilacak Git
```

Lisensi template tetap tersedia pada [template_styles/LICENSE](template_styles/LICENSE).
