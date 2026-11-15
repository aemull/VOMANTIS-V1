# **Product Requirements Document (PRD)**

# **1\. Visi dan Tujuan**

* **Nama Produk:** VOMANTIS

* **Masalah (Problem Statement):** Lamanya sinkronisasi data hasil maintenance terbaru yang menyebabkan lambatnya penjadwalan dan menurunnya akurasi perbaikan rutin mesin. Selain itu, terdapat isu pencatatan ID mesin yang duplikat atau tidak unik (berdasarkan riwayat data lama), yang menyulitkan pelacakan historis tiap unit mesin. Hal ini berisiko menyebabkan mesin berhenti beroperasi tak terduga (downtime) dan mengganggu jalannya produksi.

* **Solusi:** Sebuah aplikasi web yang dapat menyimpan data master aset secara unik, menyimpan informasi riwayat maintenance, serta memiliki fitur penjadwalan maintenance secara otomatis (berbasis waktu untuk MVP, berbasis AI untuk masa depan) dan sistem manajemen tiket tugas (Work Order) yang terstruktur.

# **2\. Target Pengguna**

* **Manager (Admin/Supervisor):** Berfokus pada pemantauan, pengelolaan master data, pembuatan/persetujuan jadwal, dan kontrol kualitas hasil perbaikan.

* **Teknisi (Operator Lapangan):** Berfokus pada pelaksanaan tugas dari tiket yang diberikan dan menginput data riwayat maintenance secara akurat (kondisi sebelum, kerusakan, dan kondisi sesudah).

* **Konteks Penggunaan & UI/UX:** Aplikasi berbasis *Web* (Web-based) yang responsif (desktop untuk Manager, mobile untuk Teknisi di lapangan). Antarmuka harus sangat sederhana, *to the point*, tombol berukuran besar untuk kemudahan tap di HP, dan alur kerja yang intuitif tanpa perlu membaca manual.

# **C. Ruang Lingkup dan Fitur (MVP)**

**1\. Dashboard Admin**

1. Menampilkan rangkuman tiket berdasarkan tingkat keparahan, jadwal maintenance rutin  
2. Statistik kerusakan dan perbaikan mesin  
3. Membuat seperti kanban board untuk tracking teknisi dan mesin yang sedang dimaintain

**1\. Modul Master Data Mesin:**

1. Tambah, Edit, Hapus (Non-aktifkan/Retired) data mesin (khusus Manager).  
2. Menampilkan informasi, history perbaikan, kondisi mesin, gambar mesin.  
3. Wajib menggunakan ID unik (gabungan kode unik/serial number per fisik mesin).  
4. Satu mesin memiliki satu QR khusus untuk mengakses informasinya.

**2\. Modul Penjadwalan & Tiket / Work Order (Manager):**

1. Sistem otomatis menjadwalkan maintenance rutin (siklus sebulan sekali).  
2. Manajer dapat menentukan tingkat kerusakan mesin secara manual.  
3. Manajer dapat menugaskan (*assign*) tiket ke Teknisi tertentu.

**2\. Dashboard Teknisi**

1. Berisi menu untuk melihat info mesin, tiket yang diterima teknisi, dan jadwal/tiket yang sedang berjalan.  
   **3\. Modul Eksekusi Maintenance (Teknisi):**

1. Form input berbasis kartu (card-based): Mengisi kondisi mesin sebelum perbaikan beserta foto/video bukti, detail kerusakan, tindakan perbaikan, dan kondisi mesin setelah perbaikan dengan lampiran foto/video.  
2. Setiap poin kerusakan/tindakan dibuat sebagai kartu terpisah yang memiliki area unggah  (foto/video kerusakan dan foto video hasil perbaikan) masing-masing.  
   **4\. Modul Approval (Manager):**

1. Menyetujui (*Approve*) laporan dari teknisi jika perbaikan sudah tuntas (status tiket menjadi Selesai).  
2. Mengembalikan tiket (*Reject/Revisi*) jika perbaikan dirasa belum tuntas, dilengkapi dengan kolom catatan revisi.  
   **5\. Fitur Masa Depan (Nice-to-have):**

1. Penjadwalan Pintar (AI): Mempertimbangkan jam operasional, tingkat kerusakan, dan kerumitan.  
2. Penentuan tingkat kerusakan secara otomatis dengan AI.

# **4\. Alur Pengguna dan Fitur (User Flow Lengkap)**

* **Alur Manager:**

  * 1\. Login ke sistem.

  * 2\. Masuk ke Dashboard (melihat ringkasan mesin dan jadwal terdekat).

  * 3\. Mengelola Master Mesin (jika ada mesin baru).

  * 4\. Membuka laporan spesifik & menentukan tingkat kerusakan secara manual.

  * 5\. Mengkonfirmasi jadwal maintenance dan menetapkan (*assign*) teknisi.

  * 6\. Tiket masuk ke akun Teknisi.

  * 7\. Menerima notifikasi/laporan selesai dari Teknisi.

  * 8\. Melakukan peninjauan: Menyetujui (*Approve*) tiket menjadi selesai, ATAU Mengembalikan tiket ke teknisi dengan catatan revisi.

* **Alur Teknisi:**

  * 1\. Login melalui peramban HP di lapangan.

  * 2\. Masuk ke Dashboard (Melihat tiket tugas yang di-*assign* ke akunnya).

  * 3\. Mengambil/membuka tiket tugas.

  * 4\. Mengambil foto dan menginput kondisi mesin saat ini (sebelum diperbaiki).

  * 5\. Melakukan perbaikan atau pengecekan fisik mesin serta mendokumentasikan setiap titik kerusakan melalui foto.

  * 6\. Menginput detail kerusakan, tindakan perbaikan, serta mengunggah foto bukti perbaikan dan foto kondisi sesudah perbaikan pada kartu masing-masing.

  * 7\. Submit laporan.

  * 8\. Menunggu persetujuan (ACC) dari Manager. (Jika dikembalikan, kerjakan ulang sesuai catatan Manager).

# **5\. Rancangan Database / Struktur Data (ERD Awal)**

* **Master\_Asset:** Asset\_ID (Unik per fisik mesin), Nama\_Mesin, Kategori, Lokasi, Status\_Aktif.

* **Users:** User\_ID, Nama\_Lengkap, Role (Manager/Teknisi), Username, Password\_Hash.

* **Jadwal\_Maintenance (Tiket):** Tiket\_ID, Asset\_ID, Tanggal\_Jadwal, Jenis\_Maintenance, Tingkat\_Kerusakan, Teknisi\_ID, Status\_Tiket.

* **Laporan\_Maintenance:** Laporan\_ID, Tiket\_ID, Tanggal\_Pengerjaan, Kondisi\_Sebelum, Foto\_Kondisi\_Sebelum, Kondisi\_Sesudah, Foto\_Kondisi\_Sesudah, Catatan\_Manager.

* **Detail\_Tindakan\_Maintenance (Kartu Kerusakan/Perbaikan):** Detail\_ID, Laporan\_ID, Detail\_Kerusakan, Foto\_Kerusakan, Tindakan\_Perbaikan, Foto\_Tindakan\_Perbaikan.

# **6\. Platform dan Kebutuhan Teknis**

* **Platform:** Web-based responsive yang nyaman untuk di mobile dan desktop

* **Integrasi Pihak Ketiga:** Tidak ada untuk saat ini (MVP).

# **7\. Metrik Kesuksesan**

* **Efisiensi Waktu:** Waktu pelaksanaan *maintenance* dapat dijadwalkan dengan presisi sehingga tidak saling bertabrakan atau mengganggu jadwal operasional produksi.

* **Akurasi Data:** Penghilangan redundansi/duplikasi ID mesin dari sistem lama untuk pelacakan aset yang akurat 100%.