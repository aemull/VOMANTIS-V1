# Hasil verifikasi

Pengujian dilakukan pada **12 November 2026 (Asia/Jakarta)**, menggunakan Windows, Python 3.14.7, Django 5.2.19, dan SQLite.

## Pemeriksaan yang lulus

- `manage.py check`: tidak ada masalah konfigurasi/model.
- `manage.py makemigrations --check --dry-run`: model sesuai dengan migrasi yang disimpan.
- `manage.py test maintenance`: **19 tes lulus**, memakai database tes dan penyimpanan bukti sementara.
- `manage.py verify_source_data`: **14 tabel, 5 baris sumber**, checksum dan snapshot cocok.
- `manage.py collectstatic --noinput`: CSS, font, ikon, dan aset template berhasil dikumpulkan.
- Scheduler lokal: pemanggilan pertama membuat 8 tiket bulanan; pemanggilan kedua menghasilkan 0 tiket baru. Database kerja kini berisi 8 mesin demo dan 16 tiket (8 demo + 8 jadwal bulanan).
- `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: 0 pelanggaran.
- Pemeriksaan browser melalui Playwright + Microsoft Edge: login Manager dan Teknisi, dashboard desktop/mobile, navigasi, halaman utama, QR SVG, validasi field wajib, tambah/hapus kartu laporan, dan tidak ada galat JavaScript/HTTP pada alur yang diuji.

## Cakupan tes otomatis

1. Semua tabel/kolom sumber tersedia pada database dan kelima baris sumber tersimpan.
2. SQL asli dipertahankan byte-per-byte, termasuk karakter × dan Σ.
3. Impor ulang idempoten; konflik isi primary key membatalkan impor tanpa menimpa data.
4. Kode lama berulang menghasilkan mesin berbeda dengan ID aplikasi unik.
5. Literal SQL dengan koma/titik koma/tanda kutip dibaca dengan benar; pernyataan tidak didukung ditolak.
6. Alur teknisi mulai → kirim → Manager revisi → teknisi kirim ulang → Manager setujui.
7. Lampiran dan snapshot versi sebelumnya tetap ada setelah revisi.
8. Lampiran wajib dan validasi foto menolak payload yang bukan gambar.
9. Teknisi lain tidak dapat membuka tiket atau bukti yang tidak ditugaskan kepadanya.
10. Teknisi tidak dapat membuat mesin, membuka arsip, atau melakukan approval.
11. Mutasi terlindungi CSRF; penonaktifan mesin hanya melalui POST.
12. Afkir mempertahankan tiket dan menonaktifkan penjadwalan baru.
13. Acuan tanggal 31 disesuaikan untuk Februari dan kembali ke 31 pada Maret.
14. Pemanggilan scheduler berulang tidak menggandakan tiket; acuan masa depan tidak dijadwalkan lebih awal.
15. Jadwal teknisi yang berbenturan ditolak oleh form dan constraint database.
16. Manager dapat membuat, mengubah jadwal, dan membatalkan tiket tanpa menghapus data.
17. Upload foto mesin, pembaruan identitas, dan keunikan serial berjalan.
18. Rumus KPI dan SUS menghasilkan nilai yang diharapkan; pembagi nol menjadi NULL.
19. Seed demo dapat diulang tanpa menggandakan data, lampiran, atau mengganti password.

20. Halaman dashboard, daftar tiket, jadwal, detail tiket, dan detail mesin tetap dapat dibuka setelah penjadwal membuat tiket tanpa teknisi.
21. Aktivitas tanpa aktor pengguna menampilkan **Sistem**; nama teknisi historis dan username akun tanpa nama lengkap tetap ditampilkan.

Beberapa skenario digabung dalam satu metode tes; jumlah metode tes adalah 19.

## Perbaikan error tiket otomatis

Template sebelumnya memakai `default:ticket.assigned_to.username` dan `default:event.actor.username`. Ketika relasi tersebut kosong, evaluasi argumen filter memicu `VariableDoesNotExist` dan HTTP 500. Tampilan kini memakai properti `assignee_name` dan `actor_name` yang menangani relasi kosong secara eksplisit.

Dua tes regresi ditambahkan setelah error berhasil direproduksi. Kelima halaman terkait juga berhasil dirender dengan respons 200 menggunakan data SQLite kerja yang sudah berisi tiket otomatis. Perbaikan ini tidak memerlukan migrasi atau perubahan data.

## Tampilan

Viewport yang diperiksa: **1440 × 1050** dan **390 × 844**. Tabel dan kanban memakai scroll di dalam komponennya; halaman tidak meluber secara horizontal pada rute yang diuji. Kontras teks pilihan dropdown dan tombol utama diperiksa setelah penyesuaian CSS Corona.

Screenshot lokal tersedia pada:

- `artifacts/browser-dashboard-desktop.png`
- `artifacts/browser-dashboard-mobile.png`
- `artifacts/browser-report-mobile.png`

## Batas verifikasi

Belum dilakukan pengujian beban banyak pengguna, pengujian di perangkat HP fisik, audit keamanan eksternal, atau deployment production. Pengujian browser mengubah session login tetapi tidak mengirim laporan atau mengubah data mesin/tiket. Detail penggunaan dan batas MVP tersedia di README dan ARCHITECTURE.
