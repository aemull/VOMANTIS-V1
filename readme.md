# Instalasi VOMANTIS di server

Panduan ini menggunakan **Debian 12 atau 13** dengan Nginx, Gunicorn, systemd, dan MariaDB atau MySQL pada satu server. Nginx menerima koneksi HTTPS, Gunicorn menjalankan aplikasi Django, dan satu layanan terpisah membuat jadwal perawatan bulanan.

Untuk instalasi baru, siapkan akun SSH dengan hak `sudo` dan akses baca ke repositori GitHub. Arahkan nama domain ke IP server dan ganti `maintenance.example.com` di semua contoh dengan domain Anda. Untuk intranet, gunakan nama DNS yang bisa diakses perangkat pengguna dan siapkan sertifikat dari CA internal.

## 1. Pasang aplikasi

Jalankan perintah berikut dari akun SSH yang akan mengelola kode aplikasi. Paket pengembangan Python dan MySQL digunakan untuk membangun driver `mysqlclient` di Debian. [Petunjuk instalasi mysqlclient](https://github.com/PyMySQL/mysqlclient#linux)

```bash
sudo apt update
sudo apt install -y git ca-certificates curl openssl nginx tzdata \
    python3 python3-venv python3-dev build-essential pkg-config default-libmysqlclient-dev

sudo useradd --system --user-group --home-dir /var/lib/vomantis \
    --no-create-home --shell /usr/sbin/nologin vomantis

umask 022
sudo install -d -m 0755 -o "$(id -un)" -g "$(id -gn)" /opt/vomantis
git clone https://github.com/aemull/VOMANTIS-V1.git /opt/vomantis/app
python3 -m venv /opt/vomantis/venv
/opt/vomantis/venv/bin/python -m pip install -r /opt/vomantis/app/requirements-production.txt

sudo install -d -o vomantis -g vomantis -m 0750 /var/lib/vomantis/media
sudo install -d -o vomantis -g vomantis -m 0755 /var/www/vomantis/static
```

Akun sistem `vomantis` menjalankan aplikasi. Direktori `/var/lib/vomantis/media` menyimpan foto mesin dan bukti laporan di luar direktori kode sehingga unggahan tetap tersedia saat aplikasi diperbarui.

## 2. Siapkan database

Untuk **MariaDB baru**, pasang server lalu masuk ke konsol SQL.

```bash
sudo apt install -y mariadb-server mariadb-client
sudo systemctl enable --now mariadb
sudo mariadb
```

Jika server sudah menggunakan **MySQL 8.4**, masuk ke konsol dengan `mysql -u root -p` dan lanjutkan dengan SQL yang sama. Ganti `GANTI_PASSWORD_DB` dengan kata sandi unik dan simpan untuk langkah 3.

```sql
CREATE DATABASE vomantis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vomantis'@'127.0.0.1' IDENTIFIED BY 'GANTI_PASSWORD_DB';
GRANT ALL PRIVILEGES ON vomantis.* TO 'vomantis'@'127.0.0.1';
EXIT;
```

Aplikasi menggunakan zona waktu `Asia/Jakarta`. Pada server database baru, muat tabel zona waktu sekali dari terminal. Untuk MariaDB, jalankan `mariadb-tzinfo-to-sql /usr/share/zoneinfo | sudo mariadb mysql`. Untuk MySQL, jalankan `mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root -p mysql`. [Dokumentasi database Django](https://docs.djangoproject.com/en/5.2/ref/databases/#time-zone-definitions)

## 3. Atur konfigurasi produksi

Buat file konfigurasi yang dapat dibaca oleh akun layanan. Gunakan hasil `openssl rand -hex 32` sebagai `DJANGO_SECRET_KEY`.

```bash
sudo install -d -o root -g vomantis -m 0750 /etc/vomantis
sudo touch /etc/vomantis/vomantis.env
sudo chown root:vomantis /etc/vomantis/vomantis.env
sudo chmod 0640 /etc/vomantis/vomantis.env
openssl rand -hex 32
sudoedit /etc/vomantis/vomantis.env
```

Isi file dengan nilai berikut. Gunakan kata sandi dari langkah 2 dan salin hasil pengacakan kunci sebagai nilai literal. `DJANGO_ALLOWED_HOSTS` berisi nama host, sedangkan `DJANGO_CSRF_TRUSTED_ORIGINS` berisi alamat lengkap dengan `https://`.

```dotenv
DB_NAME=vomantis
DB_USER=vomantis
DB_PASSWORD='GANTI_PASSWORD_DB'
DB_HOST=127.0.0.1
DB_PORT=3306

DJANGO_DEBUG=0
DJANGO_SECRET_KEY='GANTI_DENGAN_HASIL_OPENSSL'
DJANGO_ALLOWED_HOSTS=maintenance.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://maintenance.example.com
DJANGO_TRUST_PROXY=1
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_COOKIE_SECURE=1
DJANGO_STATIC_ROOT=/var/www/vomantis/static
DJANGO_MEDIA_ROOT=/var/lib/vomantis/media
```

## 4. Jalankan migrasi dan buat admin

Django otomatis membaca `.env` di sebelah `manage.py`. Untuk pengembangan lokal, salin `.env.example` ke `.env`, isi koneksi database dan buat `DJANGO_SECRET_KEY` sesuai petunjuk di file tersebut. Variabel dari proses mendapat prioritas. Di server, systemd memasok konfigurasi dari `/etc/vomantis/vomantis.env`. Definisikan fungsi `manage` berikut agar perintah di sesi SSH menggunakan konfigurasi server yang sama.

```bash
manage() {
    sudo -u vomantis /bin/sh -ec '
        set -a
        . /etc/vomantis/vomantis.env
        set +a
        cd /opt/vomantis/app
        exec /opt/vomantis/venv/bin/python manage.py "$@"
    ' sh "$@"
}

manage migrate --noinput
manage collectstatic --noinput
manage createsuperuser
manage check --deploy --database default
```

Migrasi membuat tabel aplikasi beserta grup **Manager** dan **Teknisi**. `createsuperuser` meminta kredensial admin pertama. Pemeriksaan produksi dapat menampilkan `security.W004` karena durasi HSTS belum diatur di Django. Terapkan kebijakan HSTS domain setelah HTTPS berfungsi. [Panduan deployment Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)

**Impor data lama bersifat opsional.** Jika instalasi memerlukan data dari `Main_data.sql`, jalankan kedua perintah berikut. Modul impor menyimpan arsip sumber dan perintah verifikasi memeriksa checksum serta hasil pemetaan data.

```bash
manage import_main_data /opt/vomantis/app/Main_data.sql
manage verify_source_data
```

## 5. Aktifkan aplikasi dan penjadwal

Gunakan `sudoedit` untuk membuat kedua file unit berikut.

**`/etc/systemd/system/vomantis.service`**

```ini
[Unit]
Description=Web VOMANTIS
Wants=network-online.target
After=network-online.target mariadb.service mysql.service

[Service]
User=vomantis
Group=vomantis
WorkingDirectory=/opt/vomantis/app
EnvironmentFile=/etc/vomantis/vomantis.env
ExecStart=/opt/vomantis/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 2 --timeout 120 --access-logfile - vomantis.wsgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/vomantis-scheduler.service`**

```ini
[Unit]
Description=Penjadwal perawatan VOMANTIS
Wants=network-online.target
After=network-online.target mariadb.service mysql.service

[Service]
User=vomantis
Group=vomantis
WorkingDirectory=/opt/vomantis/app
EnvironmentFile=/etc/vomantis/vomantis.env
ExecStart=/opt/vomantis/venv/bin/python -u manage.py run_scheduler --interval 3600
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vomantis.service vomantis-scheduler.service
```

Penjadwal memeriksa aset saat layanan dimulai dan setiap satu jam. Untuk setiap aset yang memenuhi jadwal, aplikasi membuat satu tiket preventif per bulan.

## 6. Hubungkan Nginx dan aktifkan HTTPS

Buat `/etc/nginx/sites-available/vomantis` dengan `sudoedit`. Nginx menyajikan `/static/` secara langsung dan meneruskan permintaan foto serta bukti laporan ke Django untuk pemeriksaan hak akses.

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name maintenance.example.com;
    client_max_body_size 128m;

    location /static/ {
        alias /var/www/vomantis/static/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

Batas `128m` berlaku untuk satu permintaan, termasuk semua lampirannya. Jika tim perlu mengirim laporan dengan 20 kartu dan 42 lampiran berukuran 25 MiB sekaligus, gunakan `1100m` untuk menampung 1.050 MiB bukti beserta data formulir.

```bash
sudo ln -s /etc/nginx/sites-available/vomantis /etc/nginx/sites-enabled/vomantis
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx
```

Pilih konfigurasi HTTPS sesuai jaringan pengguna.

**Domain publik.** Buka TCP 80 untuk validasi domain dan TCP 443 untuk pengguna. Certbot memasang sertifikat dan mengatur pengalihan ke HTTPS. [Validasi HTTP-01 Let's Encrypt](https://letsencrypt.org/docs/challenge-types/#http-01-challenge) · [Panduan Certbot untuk Nginx](https://eff-certbot.readthedocs.io/en/stable/using.html#nginx)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx --redirect -d maintenance.example.com
sudo systemctl enable --now certbot.timer
sudo certbot renew --dry-run
```

**Domain intranet dengan sertifikat internal.** Gunakan sertifikat yang dipercaya perangkat pengguna. Tambahkan direktif berikut di dalam blok `server` yang sama, sesuaikan lokasi sertifikat dan kuncinya, lalu jalankan `sudo nginx -t && sudo systemctl reload nginx`.

```nginx
listen 443 ssl;
listen [::]:443 ssl;
ssl_certificate /etc/ssl/certs/vomantis-fullchain.pem;
ssl_certificate_key /etc/ssl/private/vomantis.key;
if ($scheme = http) { return 301 https://$server_name$request_uri; }
```

## 7. Periksa hasil instalasi

```bash
sudo systemctl is-active nginx vomantis.service vomantis-scheduler.service
curl -I https://maintenance.example.com/login/
curl -I https://maintenance.example.com/static/app.css
```

Ketiga layanan seharusnya berstatus `active` dan kedua URL mengembalikan HTTP 200. Buka `/login/` melalui browser, masuk dengan admin pertama, lalu gunakan **Akun tim → Tambah akun** untuk membuat Manager dan Teknisi. Untuk memeriksa proses web atau pembuatan jadwal, jalankan `sudo journalctl -u vomantis.service -u vomantis-scheduler.service -n 50 --no-pager`.

Saat mencadangkan instalasi, simpan dump database dan isi `/var/lib/vomantis/media` dari titik waktu yang sama agar foto tetap cocok dengan catatannya. Simpan salinan `/etc/vomantis/vomantis.env` di lokasi dengan akses terbatas.
