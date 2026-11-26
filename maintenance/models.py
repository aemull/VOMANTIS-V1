import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Cast, NullIf
from django.utils import timezone


def asset_code():
    return 'VM-' + uuid.uuid4().hex[:16].upper()


def ticket_code():
    return 'WO-' + uuid.uuid4().hex[:16].upper()


def optional_text(length=255):
    return models.CharField(max_length=length, blank=True, null=True)


def decimal_field():
    return models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)


class AssetQuerySet(models.QuerySet):
    def in_master(self):
        return self.filter(deleted_at__isnull=True)


class Asset(models.Model):
    STATUS = [(s, s) for s in ['Operasional', 'Tidak Operasional', 'Perbaikan', 'Afkir']]
    CONDITIONS = [(s, s) for s in ['Baik', 'Rusak Ringan', 'Rusak Berat']]
    id_asset = models.AutoField(primary_key=True)
    asset_uid = models.CharField('ID unik mesin', max_length=40, unique=True, default=asset_code, editable=False)
    kode_asset = models.CharField('Kode aset lama', max_length=30, db_index=True)
    nama_mesin = models.CharField('Nama mesin', max_length=100)
    kategori = models.CharField(max_length=100, blank=True)
    merk = optional_text(100)
    tipe_model = optional_text(100)
    serial_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    tahun_perolehan = models.PositiveSmallIntegerField(blank=True, null=True)
    kapasitas_spesifikasi = models.TextField(blank=True, null=True)
    lokasi = optional_text(100)
    penanggung_jawab = optional_text(100)
    status = models.CharField(max_length=30, choices=STATUS, default='Operasional')
    kondisi = models.CharField(max_length=20, choices=CONDITIONS, default='Baik')
    sumber_data = optional_text(50)
    tanggal_pendataan = models.DateField(blank=True, null=True)
    petugas = optional_text(100)
    foto_link = optional_text()
    gambar = models.ImageField(upload_to='machines/%Y/%m/', blank=True)
    maintenance_anchor = models.DateField('Tanggal acuan maintenance bulanan', default=timezone.localdate)
    is_demo = models.BooleanField(default=False)
    deleted_at = models.DateTimeField('Dihapus dari master pada', blank=True, null=True, editable=False)

    objects = AssetQuerySet.as_manager()

    class Meta:
        db_table = 'master_asset'
        ordering = ['nama_mesin', 'id_asset']

    def __str__(self):
        return f'{self.asset_uid} · {self.nama_mesin}'


class AssetPhoto(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='photos')
    image = models.ImageField('Foto mesin', upload_to='machines/gallery/%Y/%m/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class InitialCondition(models.Model):
    id_kondisi = models.AutoField(primary_key=True)
    tanggal = models.DateField()
    asset = models.ForeignKey(Asset, db_column='id_asset', on_delete=models.PROTECT, related_name='initial_conditions')
    komponen_item = models.CharField(max_length=150)
    standar_kondisi = optional_text()
    kondisi_aktual = optional_text()
    ok_ng = models.CharField(max_length=2, choices=[('OK', 'OK'), ('NG', 'NG')], blank=True, null=True)
    temuan = models.TextField(blank=True, null=True)
    tindakan = models.TextField(blank=True, null=True)
    petugas = optional_text(100)
    bukti_link = optional_text()

    class Meta:
        db_table = 'kondisi_awal'


class WorkOrder(models.Model):
    STATUSES = [(s, s) for s in ['Open', 'Proses', 'Review', 'Revisi', 'Selesai', 'Batal']]
    PRIORITIES = [(s, s) for s in ['Rendah', 'Sedang', 'Tinggi', 'Darurat']]
    TYPES = [(s, s) for s in ['Korektif', 'Preventif', 'Predictive', 'Lainnya']]
    wo_number = models.CharField(primary_key=True, max_length=30, default=ticket_code)
    asset = models.ForeignKey(Asset, db_column='id_asset', on_delete=models.PROTECT, related_name='work_orders')
    tanggal_jam_lapor = models.DateTimeField(default=timezone.now)
    pelapor = optional_text(100)
    jenis = models.CharField(max_length=20, choices=TYPES, default='Korektif', blank=True, null=True)
    prioritas = models.CharField(max_length=15, choices=PRIORITIES, default='Sedang', blank=True, null=True)
    keluhan_gejala = models.TextField(blank=True, null=True)
    teknisi = optional_text(100)
    mulai_pekerjaan = models.DateTimeField(blank=True, null=True)
    selesai_pekerjaan = models.DateTimeField(blank=True, null=True)
    tindakan = models.TextField(blank=True, null=True)
    spare_part = optional_text()
    biaya = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUSES, default='Open', db_index=True)
    verifikasi = optional_text(100)
    bukti_link = optional_text()
    scheduled_date = models.DateField('Tanggal jadwal', default=timezone.localdate, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True, related_name='tickets')
    severity = models.CharField('Tingkat kerusakan', max_length=20, choices=Asset.CONDITIONS, default='Rusak Ringan')
    confirmed = models.BooleanField('Jadwal dikonfirmasi', default=False)
    monthly_key = models.CharField(max_length=60, unique=True, blank=True, null=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True, related_name='created_tickets')
    # Only active, confirmed tickets reserve a technician's date in the unique index.
    active_scheduled_date = models.GeneratedField(
        expression=models.Case(
            models.When(confirmed=True, status__in=['Open', 'Proses', 'Review', 'Revisi'], then=F('scheduled_date')),
            default=Value(None), output_field=models.DateField(),
        ),
        output_field=models.DateField(), db_persist=False, null=True,
    )

    class Meta:
        db_table = 'work_order'
        ordering = ['scheduled_date', '-tanggal_jam_lapor']
        constraints = [models.UniqueConstraint(
            fields=['assigned_to', 'active_scheduled_date'],
            name='unique_active_technician_day',
        )]

    def __str__(self):
        return self.wo_number

    @property
    def assignee_name(self):
        if self.assigned_to_id is not None:
            return self.assigned_to.get_full_name() or self.assigned_to.username
        return self.teknisi or 'Belum ditugaskan'

    @property
    def overdue(self):
        return self.scheduled_date < timezone.localdate() and self.status not in ['Selesai', 'Batal']


class FailureHistory(models.Model):
    failure_id = models.CharField(primary_key=True, max_length=30)
    asset = models.ForeignKey(Asset, db_column='id_asset', on_delete=models.PROTECT, related_name='failures')
    work_order = models.ForeignKey(WorkOrder, db_column='wo_number', on_delete=models.PROTECT, blank=True, null=True)
    tanggal_jam_mulai = models.DateTimeField()
    tanggal_jam_selesai = models.DateTimeField(blank=True, null=True)
    komponen = optional_text(150)
    gejala = models.TextField(blank=True, null=True)
    penyebab = models.TextField(blank=True, null=True)
    tindakan_perbaikan = models.TextField(blank=True, null=True)
    teknisi = optional_text(100)
    repair_time_jam = decimal_field()
    downtime_jam = decimal_field()
    biaya = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sumber_data = optional_text(50)
    bukti_link = optional_text()

    class Meta:
        db_table = 'histori_kerusakan'


class PMSchedule(models.Model):
    pm_id = models.CharField(primary_key=True, max_length=30)
    asset = models.ForeignKey(Asset, db_column='id_asset', on_delete=models.PROTECT, related_name='pm_schedules')
    item_pm = models.CharField(max_length=150)
    aktivitas = models.TextField(blank=True, null=True)
    interval = optional_text(50)
    tanggal_terjadwal = models.DateField()
    tanggal_realisasi = models.DateField(blank=True, null=True)
    hasil = models.TextField(blank=True, null=True)
    tindakan = models.TextField(blank=True, null=True)
    petugas = optional_text(100)
    status = models.CharField(max_length=20, choices=[(s, s) for s in ['Terjadwal', 'Terlaksana', 'Terlambat', 'Batal']], default='Terjadwal')
    bukti_link = optional_text()
    work_order = models.OneToOneField(WorkOrder, on_delete=models.PROTECT, blank=True, null=True, related_name='pm_schedule')

    class Meta:
        db_table = 'pm_schedule'


class Downtime(models.Model):
    downtime_id = models.CharField(primary_key=True, max_length=30)
    asset = models.ForeignKey(Asset, db_column='id_asset', on_delete=models.PROTECT, related_name='downtimes')
    tanggal = models.DateField()
    mulai_downtime = models.DateTimeField(blank=True, null=True)
    selesai_downtime = models.DateTimeField(blank=True, null=True)
    durasi_jam = decimal_field()
    penyebab = models.TextField(blank=True, null=True)
    jenis = models.CharField(max_length=10, choices=[('Planned', 'Planned'), ('Unplanned', 'Unplanned')], blank=True, null=True)
    work_order = models.ForeignKey(WorkOrder, db_column='wo_number', on_delete=models.PROTECT, blank=True, null=True)

    class Meta:
        db_table = 'downtime'


def divide(numerator, denominator):
    return Cast(F(numerator), models.FloatField()) / NullIf(F(denominator), Value(0))


class KPI(models.Model):
    id_kpi = models.AutoField(primary_key=True)
    asset = models.ForeignKey(Asset, db_column='id_asset', on_delete=models.PROTECT, related_name='kpis')
    periode = models.CharField(max_length=30)
    operating_time_jam = decimal_field()
    failure = models.IntegerField(blank=True, null=True)
    repair_time_jam = decimal_field()
    downtime_jam = decimal_field()
    pm_terjadwal = models.IntegerField(blank=True, null=True)
    pm_terlaksana = models.IntegerField(blank=True, null=True)
    mtbf_jam = models.GeneratedField(expression=divide('operating_time_jam', 'failure'), output_field=models.FloatField(), db_persist=True)
    mttr_jam = models.GeneratedField(expression=divide('repair_time_jam', 'failure'), output_field=models.FloatField(), db_persist=True)
    availability_persen = models.GeneratedField(expression=divide('operating_time_jam', 'failure') / NullIf(divide('operating_time_jam', 'failure') + divide('repair_time_jam', 'failure'), Value(0.0)) * Value(100.0), output_field=models.FloatField(), db_persist=True)
    pm_compliance_persen = models.GeneratedField(expression=divide('pm_terlaksana', 'pm_terjadwal') * Value(100.0), output_field=models.FloatField(), db_persist=True)

    class Meta:
        db_table = 'kpi_before_after'
        constraints = [models.UniqueConstraint(fields=['asset', 'periode'], name='uq_kpi')]


class UserRequirement(models.Model):
    id = models.CharField(primary_key=True, max_length=20)
    jenis = models.CharField(max_length=20, choices=[('Fungsional', 'Fungsional'), ('Non-Fungsional', 'Non-Fungsional')], blank=True, null=True)
    kebutuhan = models.TextField()
    aktor = optional_text(100)
    prioritas = models.CharField(max_length=10, choices=WorkOrder.PRIORITIES[:3], blank=True, null=True)
    kriteria_penerimaan = models.TextField(blank=True, null=True)
    status = optional_text(30)

    class Meta:
        db_table = 'user_requirement'


class Blackbox(models.Model):
    no = models.AutoField(primary_key=True)
    modul_fungsi = optional_text(100)
    skenario = models.TextField(blank=True, null=True)
    input = models.TextField(blank=True, null=True)
    expected_output = models.TextField(blank=True, null=True)
    actual_output = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=15, choices=[('Valid', 'Valid'), ('Tidak Valid', 'Tidak Valid')], blank=True, null=True)
    catatan = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'blackbox'


class UAT(models.Model):
    no = models.AutoField(primary_key=True)
    skenario = models.TextField(blank=True, null=True)
    pengguna = optional_text(100)
    hasil = models.TextField(blank=True, null=True)
    diterima_yn = models.CharField(max_length=1, choices=[('Y', 'Y'), ('N', 'N')], blank=True, null=True)
    catatan_perbaikan = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'uat'


class SUS(models.Model):
    responden = models.AutoField(primary_key=True)
    jabatan = optional_text(100)
    q1 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q2 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q3 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q4 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q5 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q6 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q7 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q8 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q9 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    q10 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    sus_score = models.GeneratedField(expression=((F('q1') + F('q3') + F('q5') + F('q7') + F('q9')) - 5 + (25 - (F('q2') + F('q4') + F('q6') + F('q8') + F('q10')))) * 2.5, output_field=models.FloatField(), db_persist=True)

    class Meta:
        db_table = 'sus'
        constraints = [models.CheckConstraint(condition=models.Q(**{f'q{i}__range': (1, 5)}), name=f'sus_q{i}_range') for i in range(1, 11)]


class Logbook(models.Model):
    id_log = models.AutoField(primary_key=True)
    tanggal = models.DateField()
    tahap = optional_text(100)
    kegiatan = models.TextField(blank=True, null=True)
    lokasi = optional_text(100)
    pelaksana = optional_text(100)
    data_output = models.TextField(blank=True, null=True)
    bukti = optional_text()
    keterangan = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'logbook_realisasi'


class EvidenceChecklist(models.Model):
    id_checklist = models.AutoField(primary_key=True)
    tahap = optional_text(100)
    bukti_minimal = models.TextField(blank=True, null=True)
    tersedia_yn = models.CharField(max_length=1, choices=[('Y', 'Y'), ('N', 'N')], default='N', blank=True, null=True)
    lokasi_file_folder = optional_text()
    catatan = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'checklist_bukti'


class IndicatorFormula(models.Model):
    indikator = models.CharField(primary_key=True, max_length=50)
    rumus = optional_text()
    keterangan = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'rumus_indikator'

    def __str__(self):
        return self.indikator


class MaintenanceReport(models.Model):
    ticket = models.OneToOneField(WorkOrder, on_delete=models.PROTECT, related_name='report')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kondisi_sebelum = models.TextField('Kondisi sebelum perbaikan')
    kondisi_sesudah = models.TextField('Kondisi setelah perbaikan')
    resulting_condition = models.CharField('Kondisi mesin hasil pemeriksaan', max_length=20, choices=Asset.CONDITIONS, default='Baik')
    submitted_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    manager_notes = models.TextField(blank=True)


class ActionCard(models.Model):
    report = models.ForeignKey(MaintenanceReport, on_delete=models.PROTECT, related_name='cards')
    komponen = models.CharField(max_length=150)
    detail_kerusakan = models.TextField('Detail kerusakan / hasil pengecekan')
    tindakan_perbaikan = models.TextField('Tindakan perbaikan')


class Attachment(models.Model):
    STAGES = [('before', 'Kondisi sebelum'), ('after', 'Kondisi sesudah'), ('damage', 'Bukti kerusakan'), ('repair', 'Bukti perbaikan')]
    report = models.ForeignKey(MaintenanceReport, on_delete=models.PROTECT, related_name='attachments')
    card = models.ForeignKey(ActionCard, on_delete=models.PROTECT, blank=True, null=True, related_name='attachments')
    stage = models.CharField(max_length=10, choices=STAGES)
    file = models.FileField(upload_to='evidence/%Y/%m/')
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(blank=True, null=True, editable=False)

    @property
    def is_video(self):
        return self.content_type.startswith('video/')


class TicketEvent(models.Model):
    ticket = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    @property
    def actor_name(self):
        if name := self.snapshot.get('actor_name'):
            return name
        if self.actor_id is None:
            return 'Sistem'
        return self.actor.get_full_name() or self.actor.username


class SourceArchive(models.Model):
    filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, unique=True)
    content = models.BinaryField()
    summary = models.JSONField(default=dict)
    imported_at = models.DateTimeField(auto_now_add=True)


class SourceRecord(models.Model):
    archive = models.ForeignKey(SourceArchive, on_delete=models.PROTECT, related_name='records')
    table_name = models.CharField(max_length=100)
    ordinal = models.PositiveIntegerField()
    payload = models.JSONField()
    object_pk = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['archive', 'table_name', 'ordinal'], name='unique_source_row')]
