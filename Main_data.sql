-- =====================================================
-- Skema Database Maintenance Digital PNC (MySQL 8 / MariaDB 10.5+)
-- Sumber: Template_Dataset_dan_Analisis_Maintenance_Digital_PNC.xlsx
-- =====================================================
CREATE DATABASE IF NOT EXISTS maintenance_pnc
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE maintenance_pnc;

-- ---------- 1. MASTER ASSET ----------
-- Catatan: kode Asset_ID pada Excel tidak unik (satu kode dipakai beberapa unit),
-- maka dipakai surrogate key id_asset; kode asli disimpan di kode_asset.
CREATE TABLE master_asset (
  id_asset              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  kode_asset            VARCHAR(30)  NOT NULL,           -- Asset_ID di Excel
  nama_mesin            VARCHAR(100) NOT NULL,
  merk                  VARCHAR(100),
  tipe_model            VARCHAR(100),
  serial_number         VARCHAR(50),
  tahun_perolehan       SMALLINT,
  kapasitas_spesifikasi TEXT,
  lokasi                VARCHAR(100),
  penanggung_jawab      VARCHAR(100),
  status                ENUM('Operasional','Tidak Operasional','Perbaikan','Afkir') DEFAULT 'Operasional',
  kondisi               ENUM('Baik','Rusak Ringan','Rusak Berat') DEFAULT 'Baik',
  sumber_data           VARCHAR(50),
  tanggal_pendataan     DATE,
  petugas               VARCHAR(100),
  foto_link             VARCHAR(255),
  UNIQUE KEY uq_serial (serial_number),
  KEY idx_kode (kode_asset)
) ENGINE=InnoDB;

-- ---------- 2. KONDISI AWAL ----------
CREATE TABLE kondisi_awal (
  id_kondisi      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  tanggal         DATE NOT NULL,
  id_asset        INT UNSIGNED NOT NULL,
  komponen_item   VARCHAR(150) NOT NULL,
  standar_kondisi VARCHAR(255),
  kondisi_aktual  VARCHAR(255),
  ok_ng           ENUM('OK','NG'),
  temuan          TEXT,
  tindakan        TEXT,
  petugas         VARCHAR(100),
  bukti_link      VARCHAR(255),
  CONSTRAINT fk_kondisi_asset FOREIGN KEY (id_asset)
    REFERENCES master_asset(id_asset) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------- 3. WORK ORDER ----------
CREATE TABLE work_order (
  wo_number         VARCHAR(30) PRIMARY KEY,
  id_asset          INT UNSIGNED NOT NULL,
  tanggal_jam_lapor DATETIME NOT NULL,
  pelapor           VARCHAR(100),
  jenis             ENUM('Korektif','Preventif','Predictive','Lainnya'),
  prioritas         ENUM('Rendah','Sedang','Tinggi','Darurat'),
  keluhan_gejala    TEXT,
  teknisi           VARCHAR(100),
  mulai_pekerjaan   DATETIME,
  selesai_pekerjaan DATETIME,
  tindakan          TEXT,
  spare_part        VARCHAR(255),
  biaya             DECIMAL(15,2) DEFAULT 0,
  status            ENUM('Open','Proses','Selesai','Batal') DEFAULT 'Open',
  verifikasi        VARCHAR(100),
  bukti_link        VARCHAR(255),
  CONSTRAINT fk_wo_asset FOREIGN KEY (id_asset)
    REFERENCES master_asset(id_asset) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------- 4. HISTORI KERUSAKAN ----------
-- wo_number opsional: tambahan agar kerusakan bisa ditautkan ke Work Order
CREATE TABLE histori_kerusakan (
  failure_id          VARCHAR(30) PRIMARY KEY,
  id_asset            INT UNSIGNED NOT NULL,
  wo_number           VARCHAR(30) NULL,
  tanggal_jam_mulai   DATETIME NOT NULL,
  tanggal_jam_selesai DATETIME,
  komponen            VARCHAR(150),
  gejala              TEXT,
  penyebab            TEXT,
  tindakan_perbaikan  TEXT,
  teknisi             VARCHAR(100),
  repair_time_jam     DECIMAL(10,2),
  downtime_jam        DECIMAL(10,2),
  biaya               DECIMAL(15,2) DEFAULT 0,
  sumber_data         VARCHAR(50),
  bukti_link          VARCHAR(255),
  CONSTRAINT fk_failure_asset FOREIGN KEY (id_asset)
    REFERENCES master_asset(id_asset) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_failure_wo FOREIGN KEY (wo_number)
    REFERENCES work_order(wo_number) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- 5. PM SCHEDULE ----------
CREATE TABLE pm_schedule (
  pm_id             VARCHAR(30) PRIMARY KEY,
  id_asset          INT UNSIGNED NOT NULL,
  item_pm           VARCHAR(150) NOT NULL,
  aktivitas         TEXT,
  `interval`        VARCHAR(50),
  tanggal_terjadwal DATE NOT NULL,
  tanggal_realisasi DATE,
  hasil             TEXT,
  tindakan          TEXT,
  petugas           VARCHAR(100),
  status            ENUM('Terjadwal','Terlaksana','Terlambat','Batal') DEFAULT 'Terjadwal',
  bukti_link        VARCHAR(255),
  CONSTRAINT fk_pm_asset FOREIGN KEY (id_asset)
    REFERENCES master_asset(id_asset) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------- 6. DOWNTIME ----------
CREATE TABLE downtime (
  downtime_id      VARCHAR(30) PRIMARY KEY,
  id_asset         INT UNSIGNED NOT NULL,
  tanggal          DATE NOT NULL,
  mulai_downtime   DATETIME,
  selesai_downtime DATETIME,
  durasi_jam       DECIMAL(10,2),
  penyebab         TEXT,
  jenis            ENUM('Planned','Unplanned'),
  wo_number        VARCHAR(30) NULL,
  CONSTRAINT fk_downtime_asset FOREIGN KEY (id_asset)
    REFERENCES master_asset(id_asset) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_downtime_wo FOREIGN KEY (wo_number)
    REFERENCES work_order(wo_number) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- 7. KPI BEFORE/AFTER ----------
-- Kolom MTBF, MTTR, Availability, PM Compliance = kolom turunan (sesuai rumus Excel)
CREATE TABLE kpi_before_after (
  id_kpi              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  id_asset            INT UNSIGNED NOT NULL,
  periode             VARCHAR(30) NOT NULL,   -- mis. 'Before' / 'After' / '2026-10'
  operating_time_jam  DECIMAL(10,2),
  failure             INT,
  repair_time_jam     DECIMAL(10,2),
  downtime_jam        DECIMAL(10,2),
  pm_terjadwal        INT,
  pm_terlaksana       INT,
  mtbf_jam  DECIMAL(10,2) GENERATED ALWAYS AS (operating_time_jam / NULLIF(failure,0)) STORED,
  mttr_jam  DECIMAL(10,2) GENERATED ALWAYS AS (repair_time_jam / NULLIF(failure,0)) STORED,
  availability_persen DECIMAL(6,2) GENERATED ALWAYS AS (
      (operating_time_jam / NULLIF(failure,0)) /
      NULLIF((operating_time_jam / NULLIF(failure,0)) + (repair_time_jam / NULLIF(failure,0)),0) * 100) STORED,
  pm_compliance_persen DECIMAL(6,2) GENERATED ALWAYS AS (pm_terlaksana / NULLIF(pm_terjadwal,0) * 100) STORED,
  UNIQUE KEY uq_kpi (id_asset, periode),
  CONSTRAINT fk_kpi_asset FOREIGN KEY (id_asset)
    REFERENCES master_asset(id_asset) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------- 8. TABEL PENDUKUNG PENELITIAN (tanpa relasi) ----------
CREATE TABLE user_requirement (
  id                  VARCHAR(20) PRIMARY KEY,
  jenis               ENUM('Fungsional','Non-Fungsional'),
  kebutuhan           TEXT NOT NULL,
  aktor               VARCHAR(100),
  prioritas           ENUM('Rendah','Sedang','Tinggi'),
  kriteria_penerimaan TEXT,
  status              VARCHAR(30)
) ENGINE=InnoDB;

CREATE TABLE blackbox (
  no              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  modul_fungsi    VARCHAR(100),
  skenario        TEXT,
  input           TEXT,
  expected_output TEXT,
  actual_output   TEXT,
  status          ENUM('Valid','Tidak Valid'),
  catatan         TEXT
) ENGINE=InnoDB;

CREATE TABLE uat (
  no                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  skenario          TEXT,
  pengguna          VARCHAR(100),
  hasil             TEXT,
  diterima_yn       ENUM('Y','N'),
  catatan_perbaikan TEXT
) ENGINE=InnoDB;

CREATE TABLE sus (
  responden  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  jabatan    VARCHAR(100),
  q1  TINYINT, q2  TINYINT, q3 TINYINT, q4 TINYINT, q5 TINYINT,
  q6  TINYINT, q7  TINYINT, q8 TINYINT, q9 TINYINT, q10 TINYINT,
  sus_score DECIMAL(5,2) GENERATED ALWAYS AS (
    ((q1 + q3 + q5 + q7 + q9) - 5 + (25 - (q2 + q4 + q6 + q8 + q10))) * 2.5) STORED,
  CONSTRAINT chk_sus CHECK (
    q1 BETWEEN 1 AND 5 AND q2 BETWEEN 1 AND 5 AND q3 BETWEEN 1 AND 5 AND q4 BETWEEN 1 AND 5 AND
    q5 BETWEEN 1 AND 5 AND q6 BETWEEN 1 AND 5 AND q7 BETWEEN 1 AND 5 AND q8 BETWEEN 1 AND 5 AND
    q9 BETWEEN 1 AND 5 AND q10 BETWEEN 1 AND 5)
) ENGINE=InnoDB;

CREATE TABLE logbook_realisasi (
  id_log      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  tanggal     DATE NOT NULL,
  tahap       VARCHAR(100),
  kegiatan    TEXT,
  lokasi      VARCHAR(100),
  pelaksana   VARCHAR(100),
  data_output TEXT,
  bukti       VARCHAR(255),
  keterangan  TEXT
) ENGINE=InnoDB;

CREATE TABLE checklist_bukti (
  id_checklist       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  tahap              VARCHAR(100),
  bukti_minimal      TEXT,
  tersedia_yn        ENUM('Y','N') DEFAULT 'N',
  lokasi_file_folder VARCHAR(255),
  catatan            TEXT
) ENGINE=InnoDB;

CREATE TABLE rumus_indikator (
  indikator  VARCHAR(50) PRIMARY KEY,
  rumus      VARCHAR(255),
  keterangan TEXT
) ENGINE=InnoDB;

INSERT INTO rumus_indikator VALUES
 ('MTBF','Operating Time / Failure','Waktu operasi rata-rata antar kegagalan'),
 ('MTTR','Total Repair Time / Failure','Waktu rata-rata perbaikan'),
 ('Availability','MTBF / (MTBF + MTTR) × 100%','Ketersediaan teoritis berdasarkan MTBF dan MTTR'),
 ('Downtime','Σ Durasi mesin tidak beroperasi','Total waktu downtime'),
 ('PM Compliance','PM terlaksana / PM terjadwal × 100%','Kepatuhan pelaksanaan preventive maintenance');