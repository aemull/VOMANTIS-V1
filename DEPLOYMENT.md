# Instalasi fresh VOMANTIS di server Debian kosong

Skrip `scripts/setup-debian.sh` menyiapkan server khusus VOMANTIS dengan **Debian 12 atau 13**, systemd, akses root/sudo, serta koneksi internet. Paket MariaDB berasal dari repositori Debian. Aplikasi memakai backend MySQL Django dan driver mysqlclient untuk mengakses MariaDB, sesuai [dokumentasi Django](https://docs.djangoproject.com/en/5.2/ref/databases/#mariadb-notes).

## 1. Kirim proyek ke server kosong

Unggah seluruh kode proyek, termasuk `maintenance/migrations/` dan `template_styles/template/assets/`, misalnya ke `/root/VOMANTIS`. Jangan unggah `.venv`, `.git`, `.env`, `artifacts/`, database SQLite, atau media lama. `Main_data.sql` tidak diperlukan untuk instalasi fresh. Skrip juga mengecualikan file tersebut saat menyalin aplikasi. Tidak perlu Node.js/npm.

Jika login sebagai root, perintah dapat dijalankan tanpa `sudo`. Jika `sudo` belum terpasang, gunakan `su -` untuk masuk root.

## 2. Jalankan setup

Untuk domain publik, arahkan DNS A (dan AAAA jika digunakan) ke server, lalu izinkan port **80 dan 443** pada firewall server/provider. Port SSH tetap mengikuti konfigurasi server. Jalankan:

```bash
cd /root/VOMANTIS
bash scripts/setup-debian.sh --host maintenance.example.com --email admin@example.com
```

Ganti domain/email dengan milik Anda. HTTPS menggunakan Let's Encrypt dan pembaruan sertifikat otomatis. Domain harus dapat diakses dari internet untuk validasi sertifikat. Jika sertifikat gagal diterbitkan, perbaiki DNS/firewall lalu ulangi perintah yang sama.

Untuk server internal yang diakses lewat alamat IP, gunakan mode HTTP secara eksplisit:

```bash
bash scripts/setup-debian.sh --host 192.168.1.10 --http
```

Mode HTTP ditujukan untuk LAN tepercaya: lalu lintas login belum dienkripsi, cookie secure dimatikan. `DEBUG` tetap mati. Skrip tidak mengubah firewall dan tidak membuka port database ke jaringan.

Skrip memasang dependensi Python, MariaDB, Nginx, Gunicorn, virtual environment, migrasi skema database, grup peran Manager/Teknisi, static files, dan penjadwal. Database aplikasi dimulai kosong: tidak ada mesin, tiket, laporan, lampiran, akun demo, fixture, atau impor `Main_data.sql`. Seeder demo sudah dihapus dari proyek. Password database serta secret key dibuat acak. Tidak ada akun/password demo yang dibuat. Setup menjalankan `seed_admin` untuk membuat satu akun administrator, kemudian Anda dapat membuka `/admin/` untuk membuat akun Manager dan Teknisi.

### Seeder akun admin

Saat setup, username default adalah `admin`; masukkan password dan konfirmasinya saat diminta. Password mengikuti validator Django dan tidak memiliki nilai bawaan. Tidak ada mesin, tiket, laporan, atau akun teknisi yang dibuat oleh seeder.

Untuk username/email lain atau instalasi tanpa prompt dari seeder, jalankan sebagai root dengan environment berikut. `read -s` menyembunyikan input password dan menghindari penyimpanannya dalam riwayat perintah:

```bash
export DJANGO_SUPERUSER_USERNAME=admin
export DJANGO_SUPERUSER_EMAIL=admin@example.com
read -rsp 'Password admin: ' DJANGO_SUPERUSER_PASSWORD; echo
export DJANGO_SUPERUSER_PASSWORD
bash scripts/setup-debian.sh --host 192.168.1.10 --http
unset DJANGO_SUPERUSER_PASSWORD
```

Seeder dapat dijalankan sendiri dengan `sudo vomantis-manage seed_admin --username admin`. Jika admin tersebut sudah ada, password dan profilnya tidak berubah. Username yang sudah dipakai akun biasa atau akun nonaktif ditolak, tanpa mengubah hak aksesnya. Password admin tidak ditulis ke file environment service. Opsi `--skip-admin` pada installer hanya diperlukan ketika akan memulihkan akun dari backup.

## 3. Lokasi dan service

| Komponen | Lokasi / nama |
| --- | --- |
| Kode aplikasi | `/opt/vomantis/app` |
| Virtual environment | `/opt/vomantis/venv` |
| Konfigurasi dan rahasia | `/etc/vomantis/vomantis.env` (root, mode 0600) |
| Database dan user | `vomantis`, koneksi `127.0.0.1:3306`, InnoDB, utf8mb4 |
| Foto dan lampiran | `/var/lib/vomantis/media` |
| Static files | `/var/www/vomantis/static` |
| Aplikasi | `vomantis.service` |
| Penjadwal | `vomantis-scheduler.timer` dan `vomantis-scheduler.service` |
| Konfigurasi Nginx | `/etc/nginx/sites-available/vomantis` |
| Perintah Django | `sudo vomantis-manage <perintah>` |

Gunicorn berjalan sebagai user sistem `vomantis`, di belakang Nginx melalui Unix socket. Media tetap dilayani oleh view Django yang memeriksa login/hak akses. Timer berjalan setiap jam dan saat setup; tanggal jadwal memakai Asia/Jakarta dari konfigurasi Django. Service serta timer aktif kembali setelah reboot. Jangan menjalankan `run_scheduler` atau cron tambahan di server ini.

```bash
sudo systemctl status vomantis vomantis-scheduler.timer --no-pager
sudo journalctl -u vomantis -u vomantis-scheduler -n 100 --no-pager
sudo systemctl list-timers vomantis-scheduler.timer
sudo vomantis-manage check --database default
```

Skrip bisa diulang dengan host/protokol yang sama: kredensial dipertahankan, migrasi tidak menggandakan data, media tidak ditimpa, dan konfigurasi Nginx hasil Certbot tetap dipakai. Sebelum pembaruan, buat backup. Skrip menghentikan aplikasi/penjadwal saat mengganti kode dan migrasi. Jika pembaruan gagal pada tahap tersebut, service dibiarkan berhenti agar skema yang belum selesai tidak dipakai; perbaiki error lalu jalankan kembali. Perubahan domain/protokol pada instalasi yang sudah ada perlu dilakukan manual pada environment, Nginx, dan sertifikat.

## 4. Pemindahan data lama (opsional, bukan instalasi fresh)

Mengganti konfigurasi tidak otomatis memindahkan isi `db.sqlite3`. Untuk instalasi fresh siap pakai, lewati seluruh bagian ini dan mulai masukkan data asli melalui aplikasi. Untuk mempertahankan akun, tiket, histori, serta foto lama:

1. Hentikan server dan scheduler lama selama ekspor hingga perpindahan selesai. Backup `db.sqlite3` dan `media/` bersamaan.
2. Di Windows, gunakan kode terbaru, salin database, lalu migrasikan **salinannya** sebelum mengekspor. Database asal tetap utuh:

```powershell
New-Item -ItemType Directory -Force artifacts | Out-Null
Copy-Item db.sqlite3 artifacts/migration-source.sqlite3
$env:DB_ENGINE = 'sqlite'
$env:SQLITE_PATH = "$PWD/artifacts/migration-source.sqlite3"
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude sessions --indent 2 --output artifacts/vomantis-data.json.gz
Remove-Item Env:SQLITE_PATH
Remove-Item Env:DB_ENGINE
```

3. Siapkan server tujuan dengan `--skip-admin` agar akun lama dapat dipulihkan tanpa konflik, misalnya:

```bash
bash scripts/setup-debian.sh --host maintenance.example.com --email admin@example.com --skip-admin
systemctl stop vomantis-scheduler.timer vomantis-scheduler.service vomantis.service
```

4. Salin `vomantis-data.json.gz` ke `/var/lib/vomantis/`, dan **isi** direktori media lama ke `/var/lib/vomantis/media/` (jangan menjadi `media/media/`). Gunakan database tujuan baru yang belum diisi aktivitas pengguna; jangan membuat akun admin sebelum impor. Jangan memakai `flush` terhadap database operasional.

```bash
chown vomantis:www-data /var/lib/vomantis/vomantis-data.json.gz
chmod 0600 /var/lib/vomantis/vomantis-data.json.gz
chown -R vomantis:www-data /var/lib/vomantis/media
vomantis-manage loaddata /var/lib/vomantis/vomantis-data.json.gz
vomantis-manage create_roles
vomantis-manage verify_source_data
vomantis-manage check --database default
systemctl start vomantis.service
systemctl start vomantis-scheduler.service
systemctl start vomantis-scheduler.timer
```

Periksa jumlah mesin/tiket, login akun lama, histori, dan akses foto/lampiran sebelum mengalihkan pengguna ke server baru. Password akun lama tetap berlaku. File fixture memuat hash password dan data operasional, jadi simpan secara privat dan hapus salinan transfer setelah verifikasi. Bila impor gagal, biarkan server tujuan berhenti, periksa konflik data, dan pertahankan database asal sebagai jalur pemulihan.

## 5. Backup

Backup database MariaDB, seluruh media, environment, dan kode yang sesuai dalam satu periode tanpa penulisan aplikasi. Contoh sebagai root (direktori backup privat):

```bash
install -d -m 0700 /var/backups/vomantis
systemctl stop vomantis-scheduler.timer vomantis-scheduler.service vomantis.service
umask 077
backup_dir="/var/backups/vomantis/$(date +%Y%m%d-%H%M%S)"
mkdir "$backup_dir"
mariadb-dump --single-transaction --routines --triggers vomantis > "$backup_dir/database.sql"
tar -czf "$backup_dir/files.tar.gz" /var/lib/vomantis/media /etc/vomantis /opt/vomantis/app
systemctl start vomantis.service vomantis-scheduler.timer
```

Pastikan dump dan arsip berhasil sebelum menganggap backup valid; jika perintah gagal, periksa error dan aktifkan kembali service secara manual setelah aman. Simpan salinan backup di tempat lain. Pemulihan dilakukan saat aplikasi/penjadwal berhenti: impor dump memakai `mariadb vomantis < database.sql`, pulihkan media beserta izin user `vomantis`, lalu jalankan kode dengan versi/migrasi yang sesuai. Uji pemulihan pada lingkungan terpisah.

## 6. Pengujian MariaDB

Jalankan tes pada lingkungan pengembangan/CI, bukan pada server produksi. User pengujian memerlukan hak membuat/menghapus database `test_vomantis` (user produksi dari skrip hanya memiliki hak pada `vomantis.*`). Jalankan `python manage.py test maintenance` dengan environment MariaDB. Tes menggunakan database terpisah dan media sementara.

Aturan satu tiket aktif terkonfirmasi per teknisi per hari memakai generated column tanggal aktif dan unique constraint gabungan. Status Selesai/Batal atau jadwal belum dikonfirmasi menghasilkan `NULL`, sehingga slot dapat digunakan kembali. Pola ini mempertahankan pemeriksaan di database pada MariaDB, yang tidak mendukung partial unique index; lihat [generated columns MariaDB](https://mariadb.com/docs/server/reference/sql-statements/data-definition/create/generated-columns).
