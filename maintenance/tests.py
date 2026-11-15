import hashlib
import io
import tempfile
from datetime import date
from pathlib import Path
from PIL import Image
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction, connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .forms import WorkOrderForm, validate_evidence
from .models import (Asset, WorkOrder, MaintenanceReport, Attachment, TicketEvent, SourceArchive,
                     SourceRecord, IndicatorFormula, KPI, SUS, PMSchedule)
from .services import generate_monthly
from .source_import import import_source, parse_source, verify_archive


def photo(name='proof.png'):
    output = io.BytesIO()
    Image.new('RGB', (4, 4), 'green').save(output, 'PNG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')


class SourcePreservationTests(TestCase):
    def test_entire_original_schema_and_all_rows_preserved_and_repeatable(self):
        path = settings.BASE_DIR / 'Main_data.sql'
        raw = path.read_bytes()
        archive, created = import_source(path)
        self.assertTrue(created)
        self.assertEqual(bytes(archive.content), raw)
        self.assertEqual(archive.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(verify_archive(archive), (14, 5))
        self.assertEqual(IndicatorFormula.objects.count(), 5)
        self.assertIn('×', IndicatorFormula.objects.get(pk='Availability').rumus)
        self.assertIn('Σ', IndicatorFormula.objects.get(pk='Downtime').rumus)
        with connection.cursor() as cursor:
            for table, expected in archive.summary['tables'].items():
                cursor.execute(f'PRAGMA table_info("{table}")')
                # SQLite table_info omits generated columns; table_xinfo includes them.
                cursor.execute(f'PRAGMA table_xinfo("{table}")')
                actual = {row[1] for row in cursor.fetchall()}
                self.assertTrue(set(expected).issubset(actual), table)
        same, created = import_source(path)
        self.assertFalse(created)
        self.assertEqual(same.pk, archive.pk)
        self.assertEqual(SourceRecord.objects.count(), 5)
        self.assertEqual(path.read_bytes(), raw)

    def test_conflicting_source_rolls_back_instead_of_overwriting(self):
        import_source(settings.BASE_DIR / 'Main_data.sql')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.sql'
            path.write_bytes((settings.BASE_DIR / 'Main_data.sql').read_bytes().replace(b'Operating Time / Failure', b'Changed Formula'))
            with self.assertRaises(ValueError):
                import_source(path)
        self.assertEqual(SourceArchive.objects.count(), 1)
        self.assertEqual(IndicatorFormula.objects.get(pk='MTBF').rumus, 'Operating Time / Failure')

    def test_duplicate_legacy_codes_are_retained_as_distinct_assets(self):
        raw = b"CREATE TABLE master_asset (id_asset INT, kode_asset VARCHAR(30), nama_mesin VARCHAR(100)); INSERT INTO master_asset VALUES (10,'SAME','Unit A'),(11,'SAME','Unit B');"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'assets.sql'
            path.write_bytes(raw)
            archive, _ = import_source(path)
        self.assertEqual(Asset.objects.filter(kode_asset='SAME').count(), 2)
        self.assertEqual(len(set(Asset.objects.values_list('asset_uid', flat=True))), 2)
        self.assertEqual(verify_archive(archive), (1, 2))

    def test_literals_and_unsupported_statements_fail_closed(self):
        raw = b"CREATE TABLE rumus_indikator (indikator VARCHAR(50),rumus TEXT,keterangan TEXT); INSERT INTO rumus_indikator VALUES ('A', 'a,b; c', 'it''s -- a string');"
        _, rows = parse_source(raw)
        self.assertEqual(rows[0][1]['keterangan'], "it's -- a string")
        with self.assertRaises(ValueError):
            parse_source(raw + b'DELETE FROM rumus_indikator;')


class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        manager_group = Group.objects.create(name='Manager')
        tech_group = Group.objects.create(name='Teknisi')
        cls.manager = get_user_model().objects.create_user('manager-test', password='TestPassword!123')
        cls.manager.groups.add(manager_group)
        cls.tech = get_user_model().objects.create_user('tech-test', password='TestPassword!123')
        cls.tech.groups.add(tech_group)
        cls.other = get_user_model().objects.create_user('other-test', password='TestPassword!123')
        cls.other.groups.add(tech_group)
        cls.asset = Asset.objects.create(kode_asset='LEGACY', nama_mesin='Mesin uji', maintenance_anchor=date(2026, 1, 31))
        cls.ticket = WorkOrder.objects.create(asset=cls.asset, assigned_to=cls.tech, confirmed=True, scheduled_date=date(2026, 11, 12))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp.cleanup)

    def payload(self, include_files=True, card_id=None):
        data = {'kondisi_sebelum': 'Bearing berisik', 'kondisi_sesudah': 'Mesin berputar normal', 'resulting_condition': 'Baik',
                'cards-TOTAL_FORMS': '1', 'cards-INITIAL_FORMS': '1' if card_id else '0', 'cards-MIN_NUM_FORMS': '1', 'cards-MAX_NUM_FORMS': '20',
                'cards-0-komponen': 'Bearing', 'cards-0-detail_kerusakan': 'Bearing aus', 'cards-0-tindakan_perbaikan': 'Ganti bearing'}
        if card_id:
            data['cards-0-id'] = str(card_id)
        if include_files:
            data.update({'before_file': photo('before.png'), 'after_file': photo('after.png'),
                         'cards-0-damage_file': photo('damage.png'), 'cards-0-repair_file': photo('repair.png')})
        return data

    def start_and_submit(self):
        self.client.force_login(self.tech)
        response = self.client.post(reverse('ticket_start', args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse('report_edit', args=[self.ticket.pk]), self.payload())
        self.assertEqual(response.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'Review')

    def test_full_submission_revision_and_approval_preserves_evidence_and_snapshots(self):
        self.start_and_submit()
        report = MaintenanceReport.objects.get(ticket=self.ticket)
        self.assertEqual(report.attachments.count(), 4)
        self.client.force_login(self.manager)
        self.client.post(reverse('ticket_review', args=[self.ticket.pk]), {'decision': 'reject', 'notes': ''})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'Review')
        self.client.post(reverse('ticket_review', args=[self.ticket.pk]), {'decision': 'reject', 'notes': 'Uji beban ulang'})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'Revisi')
        self.client.force_login(self.tech)
        data = self.payload(include_files=False, card_id=report.cards.get().pk)
        data['kondisi_sesudah'] = 'Normal setelah uji beban'
        self.assertEqual(self.client.post(reverse('report_edit', args=[self.ticket.pk]), data).status_code, 302)
        self.assertEqual(report.attachments.count(), 4)
        submissions = TicketEvent.objects.filter(ticket=self.ticket, action='Laporan dikirim untuk review').order_by('pk')
        self.assertEqual(submissions.count(), 2)
        self.assertEqual(submissions.first().snapshot['kondisi_sesudah'], 'Mesin berputar normal')
        self.assertEqual(submissions.last().snapshot['kondisi_sesudah'], 'Normal setelah uji beban')
        self.client.force_login(self.manager)
        self.client.post(reverse('ticket_review', args=[self.ticket.pk]), {'decision': 'approve', 'notes': 'Lulus uji'})
        self.ticket.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual(self.ticket.status, 'Selesai')
        self.assertIsNotNone(self.ticket.selesai_pekerjaan)
        self.assertEqual(self.asset.kondisi, 'Baik')
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse('report_edit', args=[self.ticket.pk])).status_code, 403)

    def test_roles_scope_files_and_review_permissions(self):
        self.start_and_submit()
        evidence = Attachment.objects.first()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('ticket_detail', args=[self.ticket.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('attachment', args=[evidence.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('asset_create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('source_data')).status_code, 403)
        self.assertEqual(self.client.post(reverse('ticket_review', args=[self.ticket.pk]), {'decision': 'approve'}).status_code, 403)
        self.client.force_login(self.tech)
        response = self.client.get(reverse('attachment', args=[evidence.pk]))
        self.assertEqual(response.status_code, 200)
        response.close()
        self.client.logout()
        self.assertEqual(self.client.get(reverse('attachment', args=[evidence.pk])).status_code, 302)

    def test_evidence_required_and_invalid_upload_rejected(self):
        self.client.force_login(self.tech)
        self.client.post(reverse('ticket_start', args=[self.ticket.pk]))
        response = self.client.post(reverse('report_edit', args=[self.ticket.pk]), self.payload(False))
        self.assertContains(response, 'Lampiran bukti wajib')
        self.assertEqual(MaintenanceReport.objects.count(), 0)
        data = self.payload()
        data['before_file'] = SimpleUploadedFile('malware.png', b'not an image', content_type='image/png')
        self.assertContains(self.client.post(reverse('report_edit', args=[self.ticket.pk]), data), 'Foto tidak valid')
        self.assertEqual(MaintenanceReport.objects.count(), 0)

    def test_unconfirmed_ticket_cannot_be_started(self):
        self.ticket.confirmed = False
        self.ticket.save()
        self.client.force_login(self.tech)
        self.client.post(reverse('ticket_start', args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'Open')

    def test_retire_is_post_only_and_never_deletes_history(self):
        self.client.force_login(self.manager)
        url = reverse('asset_retire', args=[self.asset.asset_uid])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, 'Afkir')
        self.assertTrue(WorkOrder.objects.filter(pk=self.ticket.pk).exists())
        self.assertEqual(generate_monthly(date(2026, 12, 1)), 0)

    def test_schedule_end_of_month_and_idempotence(self):
        self.assertEqual(generate_monthly(date(2026, 2, 1)), 1)
        self.assertEqual(generate_monthly(date(2026, 2, 10)), 0)
        ticket = WorkOrder.objects.get(monthly_key=f'{self.asset.pk}:2026-02')
        self.assertEqual(ticket.scheduled_date, date(2026, 2, 28))
        self.assertFalse(ticket.confirmed)
        self.assertEqual(PMSchedule.objects.filter(work_order=ticket).count(), 1)
        self.assertEqual(generate_monthly(date(2026, 3, 1)), 1)
        self.assertEqual(WorkOrder.objects.get(monthly_key=f'{self.asset.pk}:2026-03').scheduled_date.day, 31)
        future = Asset.objects.create(kode_asset='FUTURE', nama_mesin='Future', maintenance_anchor=date(2027, 1, 1))
        self.assertEqual(generate_monthly(date(2026, 3, 1)), 0)

    def test_technician_collision_is_rejected(self):
        form = WorkOrderForm(data={'asset': self.asset.pk, 'jenis': 'Preventif', 'prioritas': 'Sedang', 'severity': 'Baik',
            'scheduled_date': '2026-11-12', 'assigned_to': self.tech.pk, 'confirmed': True, 'keluhan_gejala': 'Check', 'biaya': 0})
        self.assertFalse(form.is_valid())
        self.assertIn('scheduled_date', form.errors)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkOrder.objects.create(asset=self.asset, assigned_to=self.tech, confirmed=True,
                                     scheduled_date=self.ticket.scheduled_date, status='Proses')

    def test_manager_can_create_edit_and_cancel_without_erasing_ticket(self):
        self.client.force_login(self.manager)
        payload = {'asset': self.asset.pk, 'jenis': 'Korektif', 'prioritas': 'Tinggi', 'severity': 'Rusak Ringan',
                   'scheduled_date': '2026-11-13', 'assigned_to': self.tech.pk, 'confirmed': 'on',
                   'keluhan_gejala': 'Periksa motor', 'spare_part': 'Bearing', 'biaya': '120000.00'}
        response = self.client.post(reverse('ticket_create'), payload)
        self.assertEqual(response.status_code, 302)
        ticket = WorkOrder.objects.get(keluhan_gejala='Periksa motor')
        self.assertEqual(ticket.created_by, self.manager)
        payload['scheduled_date'] = '2026-11-14'
        self.assertEqual(self.client.post(reverse('ticket_edit', args=[ticket.pk]), payload).status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.scheduled_date, date(2026, 11, 14))
        self.client.post(reverse('ticket_cancel', args=[ticket.pk]), {'notes': 'Digabung ke perawatan bulan depan'})
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'Batal')
        self.assertEqual(ticket.events.count(), 3)

    def test_manager_asset_form_keeps_identity_and_validates_unique_serial(self):
        self.client.force_login(self.manager)
        payload = {'kode_asset': 'LEGACY', 'nama_mesin': 'Mesin baru', 'serial_number': 'SN-UNIQUE', 'kategori': 'Uji',
                   'status': 'Operasional', 'kondisi': 'Baik', 'maintenance_anchor': '2026-11-10', 'gambar': photo('machine.png')}
        self.assertEqual(self.client.post(reverse('asset_create'), payload).status_code, 302)
        asset = Asset.objects.get(serial_number='SN-UNIQUE')
        uid = asset.asset_uid
        payload.pop('gambar')
        payload['nama_mesin'] = 'Mesin diperbarui'
        self.assertEqual(self.client.post(reverse('asset_edit', args=[uid]), payload).status_code, 302)
        asset.refresh_from_db()
        self.assertEqual(asset.asset_uid, uid)
        self.assertEqual(asset.nama_mesin, 'Mesin diperbarui')
        response = self.client.get(reverse('asset_image', args=[uid]))
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.client.post(reverse('asset_create'), payload).status_code, 200)
        self.assertEqual(Asset.objects.filter(serial_number='SN-UNIQUE').count(), 1)

    def test_all_main_pages_render_and_qr_is_real_svg(self):
        self.client.force_login(self.manager)
        urls = ['/', '/machines/', '/tickets/', '/tickets/new/', '/schedule/', '/analytics/', '/data/', '/machines/new/', '/password/',
                reverse('asset_detail', args=[self.asset.asset_uid]), reverse('ticket_detail', args=[self.ticket.pk]),
                reverse('ticket_edit', args=[self.ticket.pk]), reverse('asset_edit', args=[self.asset.asset_uid])]
        from .views import SOURCE_TABLES
        for table in SOURCE_TABLES:
            urls.extend([reverse('source_table', args=[table]), reverse('source_add', args=[table]), reverse('export_table', args=[table])])
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, follow=True).status_code, 200)
        response = self.client.get(reverse('asset_qr', args=[self.asset.asset_uid]))
        self.assertEqual(response['Content-Type'], 'image/svg+xml')
        self.assertIn(b'<svg', response.content)
        self.assertIn(b'<path', response.content)
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_generated_schedule_pages_handle_missing_technician_and_system_actor(self):
        target = timezone.localdate()
        generate_monthly(target)
        generated = WorkOrder.objects.get(monthly_key=f'{self.asset.pk}:{target:%Y-%m}')
        self.assertIsNone(generated.assigned_to)
        self.assertIsNone(generated.events.get().actor)
        self.client.force_login(self.manager)
        for url in [reverse('dashboard'), reverse('ticket_list'),
                    reverse('schedule') + f'?month={target:%Y-%m}',
                    reverse('ticket_detail', args=[generated.pk]),
                    reverse('asset_detail', args=[self.asset.asset_uid])]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'Belum ditugaskan')
        self.assertContains(self.client.get(reverse('dashboard')), 'Sistem')
        self.assertContains(self.client.get(reverse('ticket_detail', args=[generated.pk])), 'Sistem')

    def test_system_event_and_legacy_technician_names_render(self):
        TicketEvent.objects.create(ticket=self.ticket, action='Pengingat otomatis')
        self.client.force_login(self.tech)
        for url in [reverse('dashboard'), reverse('ticket_detail', args=[self.ticket.pk])]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'Sistem')
                self.assertContains(response, self.tech.username)
        legacy = WorkOrder.objects.create(asset=self.asset, teknisi='Teknisi historis')
        self.client.force_login(self.manager)
        for url in [reverse('ticket_list'), reverse('ticket_detail', args=[legacy.pk]),
                    reverse('asset_detail', args=[self.asset.asset_uid])]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'Teknisi historis')

    def test_csrf_enforced_for_mutation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        self.assertEqual(client.post(reverse('asset_retire', args=[self.asset.asset_uid])).status_code, 403)

    def test_numeric_indicators_and_null_division(self):
        kpi = KPI.objects.create(asset=self.asset, periode='Before', operating_time_jam=160, failure=4, repair_time_jam=8, pm_terjadwal=4, pm_terlaksana=3)
        kpi.refresh_from_db()
        self.assertAlmostEqual(kpi.mtbf_jam, 40)
        self.assertAlmostEqual(kpi.mttr_jam, 2)
        self.assertAlmostEqual(kpi.availability_persen, 40 / 42 * 100)
        self.assertAlmostEqual(kpi.pm_compliance_persen, 75)
        kpi.failure = 0
        kpi.pm_terjadwal = 0
        kpi.save()
        kpi.refresh_from_db()
        self.assertIsNone(kpi.mtbf_jam)
        self.assertIsNone(kpi.availability_persen)
        self.assertIsNone(kpi.pm_compliance_persen)
        sus = SUS.objects.create(**{f'q{i}': 5 if i % 2 else 1 for i in range(1, 11)})
        sus.refresh_from_db()
        self.assertEqual(sus.sus_score, 100)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SUS.objects.create(q1=6)

    def test_seed_is_repeatable_and_does_not_reset_credentials(self):
        call_command('seed_demo', password='ExamplePassword123!', stdout=io.StringIO())
        count = Asset.objects.count()
        files = Attachment.objects.count()
        call_command('seed_demo', password='DifferentPassword123!', stdout=io.StringIO())
        self.assertEqual(Asset.objects.count(), count)
        self.assertEqual(Attachment.objects.count(), files)
        self.assertTrue(get_user_model().objects.get(username='manager').check_password('ExamplePassword123!'))
