# Pemetaan data VOMANTIS

Seluruh tabel dan kolom `Main_data.sql` tersedia di MariaDB. Data tambahan menggunakan kolom atau tabel baru. SQL asli diarsipkan sebagai byte, sehingga komentar, struktur MySQL, dan isi Unicode tetap dapat dipulihkan persis.

## Tabel sumber

| Tabel MariaDB / MySQL asal | Model Django | Isi sumber | Penggunaan |
| --- | --- | ---: | --- |
| `master_asset` | `Asset` | 0 | Master mesin, serial, lokasi, kondisi, metadata sumber |
| `kondisi_awal` | `InitialCondition` | 0 | Checklist komponen dan kondisi awal |
| `work_order` | `WorkOrder` | 0 | Tiket, waktu kerja, teknisi historis, biaya, bukti |
| `histori_kerusakan` | `FailureHistory` | 0 | Gejala, penyebab, tindakan, waktu perbaikan dan downtime |
| `pm_schedule` | `PMSchedule` | 0 | Jadwal preventive, realisasi, hasil dan bukti |
| `downtime` | `Downtime` | 0 | Downtime planned / unplanned dan relasi tiket |
| `kpi_before_after` | `KPI` | 0 | Pengukuran serta MTBF, MTTR, availability dan compliance |
| `user_requirement` | `UserRequirement` | 0 | Kebutuhan fungsional / nonfungsional |
| `blackbox` | `Blackbox` | 0 | Pengujian blackbox |
| `uat` | `UAT` | 0 | User acceptance test |
| `sus` | `SUS` | 0 | Sepuluh pertanyaan dan skor SUS |
| `logbook_realisasi` | `Logbook` | 0 | Logbook pelaksanaan |
| `checklist_bukti` | `EvidenceChecklist` | 0 | Daftar bukti penelitian |
| `rumus_indikator` | `IndicatorFormula` | 5 | Definisi MTBF, MTTR, Availability, Downtime, PM Compliance |

**Jumlah sumber: 14 tabel, 5 baris.** Data DEMO dan data yang ditambahkan melalui aplikasi tidak dihitung sebagai data sumber.

SHA-256 file yang digunakan saat implementasi:

```text
1949e796471c10a1fcf223b601d7367912b2aaa41c0e2f30c953e3d4f2c2dc16
```

## Adaptasi untuk MariaDB

- `AUTO_INCREMENT` dipetakan ke primary key integer Django/MariaDB; primary key sumber tetap dipakai jika tercantum dalam INSERT.
- `ENUM` dipetakan ke field dengan pilihan tervalidasi pada form/model. Tidak ada nilai sumber yang dikurangi.
- `DECIMAL` menggunakan DecimalField. Angka finansial disimpan sampai dua angka desimal.
- Datetime sumber tanpa zona waktu ditafsirkan sebagai Asia/Jakarta dan dikelola dengan dukungan timezone Django.
- Kolom relasi tetap memakai nama asal `id_asset` atau `wo_number`; field Python bernama `asset` / `work_order`.
- Kolom KPI dan SUS menggunakan `GeneratedField(db_persist=True)`. Rumus memakai aritmetika riil untuk mencegah pembagian integer SQLite. Pembagi nol menghasilkan `NULL` sebagaimana `NULLIF` pada SQL sumber.
- Foreign key menggunakan `PROTECT` untuk mencegah hilangnya riwayat. Penghapusan data tidak disediakan dalam UI maupun Django Admin.
- Batas nilai SUS 1–5 dipertahankan melalui constraint database dan validator form; nilai kosong tetap diperbolehkan sebagaimana SQL asal.

## Tambahan untuk memenuhi PRD

| Objek | Tambahan |
| --- | --- |
| Mesin | `asset_uid` unik dan immutable, kategori, upload gambar, tanggal acuan bulanan, penanda demo |
| Work order | Tanggal jadwal, akun teknisi, tingkat kerusakan, konfirmasi, pembuat, kunci bulanan; status `Review` dan `Revisi` |
| PM | Relasi satu-ke-satu opsional ke tiket otomatis |
| `MaintenanceReport` | Kondisi sebelum/sesudah, kondisi hasil, pengirim, waktu submit, catatan Manager |
| `ActionCard` | Komponen, detail temuan dan tindakan, terhubung ke laporan |
| `Attachment` | Berkas per tahap/kartu, nama asli, MIME terverifikasi, waktu unggah |
| `TicketEvent` | Aktor, peristiwa, catatan, snapshot laporan dan ID bukti |
| `SourceArchive` | Byte SQL asli, checksum, skema dan jumlah baris |
| `SourceRecord` | Snapshot JSON setiap baris sumber dan primary key hasil impor |
| Auth Django | Akun, hash password, session, grup Manager dan Teknisi |

Kode aset lama **tidak dibuat unik**. Dua unit dengan kode lama sama tetap menjadi dua baris berbeda dengan `id_asset`, `asset_uid`, dan QR sendiri. Serial yang tidak diisi disimpan sebagai `NULL`; serial yang diisi harus unik.

## Pemeriksaan integritas

`verify_source_data` membaca ulang arsip, memverifikasi SHA-256, memastikan seluruh kolom SQL memiliki pemetaan model, membandingkan snapshot tiap baris, dan memastikan objek hasil impor masih ada. Test otomatis juga membandingkan kolom SQL lewat introspeksi database Django, termasuk kolom turunan, pada MariaDB maupun SQLite untuk uji kompatibilitas.

`import_main_data` bersifat transaksional: konflik atau struktur yang tidak didukung membatalkan keseluruhan impor. Mengimpor file identik kembali hanya memverifikasi arsip yang sudah tersedia. Penambahan dump lain dengan ID yang bentrok tidak ditimpa atau diabaikan secara diam-diam.

CSV adalah keluaran untuk pembacaan/spreadsheet, bukan pengganti arsip SQL. Sel yang diawali karakter formula diberi prefiks apostrof untuk menghindari eksekusi formula ketika dibuka di spreadsheet. SQL asli dapat diunduh dari halaman Data & arsip tanpa transformasi.
