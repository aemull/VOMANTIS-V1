# VOMANTIS

Aplikasi web maintenance mesin berbasis **Django**, menggunakan **SQLite** untuk database sementara. Antarmuka berbahasa Indonesia memakai CSS, font, dan ikon **Corona Admin** dari direktori `template_styles`. Tidak perlu menjalankan npm atau mengompilasi template.

## 1. Menjalankan aplikasi yang sudah disiapkan

Workspace ini sudah berisi `.venv`, `db.sqlite3`, data sumber yang diimpor, dan data contoh berlabel **DEMO**.

Dari PowerShell di `D:\VOMANTIS`:

```powershell
.\start.ps1
```

Buka **http://127.0.0.1:8000/**.

`start.ps1` menjalankan migrasi, memeriksa impor sumber, membuat jadwal bulan berjalan, lalu menjalankan server dan penjadwal latar belakang. Penjadwal memeriksa bulan berjalan setiap jam. Proses penjadwal dihentikan saat script/server dihentikan. Hasilnya tercatat di `scheduler.log` dan `scheduler-error.log`.

Jika kebijakan PowerShell menghalangi script, jalankan dua terminal:

```powershell
# Terminal 1: aplikasi
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

```powershell
# Terminal 2: penjadwal otomatis
.\.venv\Scripts\python.exe manage.py run_scheduler
```

**Akun demo lokal:**

| Username | Password | Peran |
| --- | --- | --- |
| `manager` | `DemoMaint!2026` | Manager |
| `teknisi` | `DemoMaint!2026` | Teknisi |
| `teknisi2` | `DemoMaint!2026` | Teknisi |

Password tersebut hanya untuk demonstrasi lokal. Gunakan akun dan password tersendiri untuk data operasional. Akun Manager demo dapat membuka `/admin/` untuk data pendukung, tetapi bukan superuser untuk pengelolaan akun Django.

## 2. Instalasi dari awal

Prasyarat: Python **3.12–3.14** dan pip. Implementasi ini diuji dengan Python 3.14 dan Django 5.2.19. Kompatibilitas Python mengikuti [catatan rilis Django 5.2](https://docs.djangoproject.com/en/5.2/releases/5.2/).

### Windows / PowerShell

```powershell
cd D:\VOMANTIS
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py create_roles
.\.venv\Scripts\python.exe manage.py import_main_data
.\.venv\Scripts\python.exe manage.py createsuperuser
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
.venv/bin/python manage.py import_main_data
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Jalankan `.venv/bin/python manage.py run_scheduler` di terminal kedua untuk mengaktifkan jadwal otomatis selama pengembangan.

`requirements-lock.txt` menyimpan versi yang dipakai saat pengujian. `requirements.txt` menyediakan rentang versi jika ingin memperbarui dependensi secara sengaja.

### Menambahkan data contoh (opsional)

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo --password 'DemoMaint!2026'
```

Perintah ini menambahkan delapan mesin, delapan work order dengan berbagai status, laporan, lampiran contoh bertuliskan DEMO, histori, downtime, dan pengukuran KPI. Akun `manager`, `teknisi`, dan `teknisi2` dibuat bila belum ada. Pemanggilan ulang tidak menggandakan data atau mengganti password akun yang sudah ada.

Jika ingin instalasi bersih untuk operasional, ikuti langkah instalasi dari awal pada salinan folder proyek tanpa `.venv`, `db.sqlite3`, atau `media` demo; jangan jalankan `seed_demo`. Jangan menghapus database yang sudah berisi data operasional.

## 3. Pengaturan akun

1. Masuk ke `http://127.0.0.1:8000/admin/` memakai superuser yang dibuat dengan `createsuperuser`.
2. Tambahkan akun pada menu **Users** dan atur password.
3. Untuk Manager, masukkan akun ke grup **Manager**. Aktifkan **Staff status** hanya jika perlu membuka Django Admin.
4. Untuk teknisi, masukkan akun ke grup **Teknisi**. Teknisi harus aktif agar muncul pada pilihan penugasan.
5. Pengguna masuk melalui `/login/`. Password dapat diganti dari menu **Ubah password**.

Superuser diperlakukan sebagai Manager pada aplikasi. Teknisi hanya dapat melihat tiket yang ditugaskan kepadanya, termasuk lampiran tiket tersebut. Informasi master mesin tersedia bagi semua pengguna yang sudah login.

## 4. Alur penggunaan

### Manager

1. **Master mesin → Tambah mesin.** Isi kode lama, nama, serial bila tersedia, kategori, lokasi, kondisi, foto, dan tanggal acuan maintenance.
2. Setiap mesin mendapat `asset_uid` unik yang tidak dapat diedit. Kode aset lama boleh berulang karena tetap diperlukan untuk pelacakan data lama. Serial yang diisi harus unik.
3. Buka detail mesin untuk informasi, riwayat, dan unduhan QR. Tombol **Nonaktifkan / Afkir** mengubah status tanpa menghapus data.
4. Buka **Jadwal maintenance**, pilih bulan, lalu buat jadwal bulanan; atau buat **Work order** korektif secara manual.
5. Buka tiket → **Atur penugasan**. Tentukan teknisi, tanggal, prioritas, tingkat kerusakan, dan centang **Jadwal dikonfirmasi**.
6. Ikuti progres pada kanban atau daftar tiket. Indikator lonceng menampilkan jumlah laporan berstatus **Review**; notifikasi bersifat di dalam aplikasi.
7. Buka laporan, periksa setiap kartu dan lampiran, lalu setujui atau kembalikan dengan catatan revisi.

### Teknisi

1. Masuk menggunakan akun teknisi dan buka **Work order saya**.
2. Buka tiket terkonfirmasi → **Mulai pekerjaan**.
3. Pilih **Isi laporan maintenance**. Isi kondisi sebelum, kondisi setelah, dan hasil pemeriksaan mesin.
4. Unggah bukti sebelum/sesudah. Tambahkan kartu untuk setiap komponen atau titik kerusakan, lengkap dengan temuan, tindakan, bukti kerusakan, dan bukti perbaikan.
5. Kirim laporan untuk review. Jika dikembalikan, baca catatan Manager, perbaiki laporan, lalu kirim kembali.

Format lampiran: JPG, JPEG, PNG, WebP, MP4, atau WebM; maksimal **25 MB per berkas**, maksimal **20 kartu** per laporan. Foto diverifikasi dengan Pillow, video diperiksa ekstensi dan signature container. Lampiran hanya dapat dibuka setelah login dan pemeriksaan hak akses. Lampiran sebelumnya tidak dihapus saat revisi. Setiap pengiriman laporan menyimpan snapshot isi kartu dan daftar lampiran dalam jejak aktivitas.

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

Pilih salah satu penjadwal. Tidak ada proses yang diam-diam didaftarkan sebagai service OS. Jika aplikasi mati melewati pergantian bulan, bulan berjalan diproses saat penjadwal kembali hidup. Bulan yang terlewat dapat dibuat secara eksplisit dengan `--month`.

## 6. Data SQL dan integritas

`Main_data.sql` asli **tidak diubah**. File yang diberikan berisi **14 tabel dan 5 baris data**, seluruh baris berada pada `rumus_indikator`; tabel mesin dan transaksi pada sumber masih kosong.

- Semua tabel dan kolom sumber dipetakan ke SQLite dengan nama tabel/kolom asal.
- Relasi mesin, work order, kondisi awal, kerusakan, PM, downtime, serta KPI tetap tersedia.
- Kolom turunan KPI dan SUS memakai generated columns SQLite.
- Byte asli SQL, SHA-256, ringkasan tabel, serta snapshot tiap baris impor disimpan dalam database.
- Impor berulang terhadap file yang sama tidak menambah duplikat. Konflik primary key dengan isi berbeda membatalkan seluruh impor, tanpa menimpa data.
- Parser membaca `CREATE TABLE` dan literal `INSERT ... VALUES`; SQL sumber tidak dieksekusi langsung. Pernyataan tidak didukung ditolak agar data tidak terlewat diam-diam.
- Penghapusan fisik dinonaktifkan pada aplikasi dan Django Admin. Relasi historis dilindungi dengan `PROTECT`.

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
.\.venv\Scripts\python.exe manage.py verify_source_data
```

Tes menggunakan database terpisah dan direktori lampiran sementara; database kerja tidak dihapus atau diubah oleh tes. Cakupan meliputi preservasi SQL, ID unik dengan kode lama berulang, batas akses per peran, akses lampiran, CSRF, alur laporan/revisi/approval, penonaktifan mesin, penjadwalan akhir bulan dan duplikasi, benturan teknisi, rumus KPI/SUS, serta rendering halaman utama.

Pemeriksaan browser opsional tersedia di `scripts/browser_check.py`. Dengan data demo dan server lokal yang aktif, pasang Playwright (`.\.venv\Scripts\python.exe -m pip install playwright`) lalu jalankan `.\.venv\Scripts\python.exe scripts/browser_check.py`. Script memakai Microsoft Edge yang terpasang, menguji desktop 1440 px dan mobile 390 px, serta menyimpan screenshot di `artifacts/`. Playwright tidak diperlukan untuk menjalankan aplikasi.

## 8. Akses dari HP di jaringan lokal

Untuk pengujian melalui HP yang terhubung Wi-Fi yang sama, sesuaikan alamat LAN komputer:

```powershell
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,192.168.1.10'
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

Buka `http://192.168.1.10:8000/` di HP. Sesuaikan izin firewall Windows untuk port tersebut pada jaringan privat. QR memuat alamat host yang dipakai saat mengunduhnya: buka halaman mesin melalui alamat LAN sebelum mengunduh QR untuk HP. QR dengan `127.0.0.1` hanya cocok untuk komputer yang sama.

## 9. Backup dan konfigurasi

Simpan **`db.sqlite3` dan seluruh direktori `media/` sebagai satu backup**. Hentikan server serta penjadwal saat menyalin file database agar backup konsisten. File sumber `Main_data.sql` juga perlu disimpan bersama proyek.

Konfigurasi melalui environment variables, tanpa pembaca `.env` otomatis:

| Variabel | Default pengembangan | Fungsi |
| --- | --- | --- |
| `DJANGO_DEBUG` | `1` | Gunakan `0` untuk deployment |
| `DJANGO_SECRET_KEY` | Kunci lokal development | Wajib diatur sendiri jika DEBUG=0 |
| `DJANGO_ALLOWED_HOSTS` | localhost, 127.0.0.1, [::1], testserver | Daftar host dipisahkan koma |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Kosong | Origin HTTPS yang dipercaya bila diperlukan |

Server `runserver` ditujukan untuk pengembangan. Deployment memerlukan server WSGI, HTTPS, `DEBUG=0`, secret key sendiri, konfigurasi static setelah `collectstatic`, dan penjadwal yang dikelola service/Task Scheduler. Jangan mempublikasikan direktori `media` langsung karena bukti disajikan lewat view yang memeriksa akses. Tidak ada deployment eksternal yang dibuat oleh proyek ini.

SQLite sesuai tahap sementara; untuk banyak teknisi yang menulis bersamaan, pertimbangkan PostgreSQL. Fitur AI dan penjadwalan berdasarkan jam operasional merupakan pengembangan lanjutan sesuai PRD.

## 10. Struktur proyek

```text
VOMANTIS/
  manage.py                  # Entry point Django
  start.ps1                  # Server + penjadwal lokal Windows
  requirements*.txt          # Dependensi
  vomantis/                  # Settings, URL, WSGI
  maintenance/
    models.py                # Semua tabel sumber + alur operasional
    views.py, forms.py       # Halaman, hak akses, validasi
    services.py              # Penjadwal dan transisi tiket
    source_import.py         # Parser, arsip, verifikasi SQL
    management/commands/     # Impor, verifikasi, peran, demo, scheduler
    migrations/              # Migrasi skema SQLite
    tests.py                 # Pengujian otomatis
  templates/                 # Template Django
  static/                    # CSS dan JavaScript aplikasi
  template_styles/           # Corona Admin asli, tetap dipertahankan
  docs/                      # Pemetaan data dan arsitektur
  Main_data.sql              # Sumber SQL asli
  PRD.md                     # Kebutuhan produk asli
  db.sqlite3                 # Database lokal, tidak dilacak Git
  media/                     # Foto dan bukti, tidak dilacak Git
```

Lisensi template tetap tersedia pada [template_styles/LICENSE](template_styles/LICENSE).
