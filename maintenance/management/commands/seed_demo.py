import io
from datetime import timedelta
from PIL import Image, ImageDraw
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from maintenance.models import Asset, WorkOrder, MaintenanceReport, ActionCard, Attachment, TicketEvent, KPI, FailureHistory, Downtime, InitialCondition
from maintenance.services import report_snapshot


class Command(BaseCommand):
    help = 'Tambahkan data contoh berlabel DEMO. Tidak menghapus / menimpa data yang ada.'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True, help='Password akun demo baru, minimal 12 karakter. Akun lama tidak diubah.')

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']
        if len(password) < 12:
            raise CommandError('Password demo minimal 12 karakter.')
        call_command('create_roles', stdout=self.stdout)
        call_command('import_main_data', stdout=self.stdout)
        users = []
        for username, name, role in [('manager', 'Aditya Pratama', 'Manager'), ('teknisi', 'Rizky Saputra', 'Teknisi'), ('teknisi2', 'Dimas Wijaya', 'Teknisi')]:
            user, created = get_user_model().objects.get_or_create(username=username)
            if created:
                user.first_name, user.last_name = name.split(' ', 1)
                user.set_password(password)
                user.is_staff = role == 'Manager'
                user.save()
                user.groups.add(Group.objects.get(name=role))
            elif not user.groups.filter(name=role).exists():
                raise CommandError(f'Akun {username} sudah ada dengan peran berbeda; demo dibatalkan tanpa mengubah akun.')
            users.append(user)
        manager, tech1, tech2 = users
        today = timezone.localdate()
        names = [
            ('Mesin Bubut CNC', 'DMG Mori', 'Turning', 'Workshop A', 'Rusak Ringan'),
            ('Mesin Frais Universal', 'DECKEL', 'Milling', 'Workshop A', 'Baik'),
            ('Kompresor Udara', 'Atlas Copco', 'Utilitas', 'Ruang Kompresor', 'Rusak Berat'),
            ('Mesin Bor Radial', 'Krisbow', 'Drilling', 'Workshop B', 'Baik'),
            ('Mesin Gerinda Datar', 'Okamoto', 'Grinding', 'Workshop B', 'Rusak Ringan'),
            ('Mesin Las TIG', 'Lincoln', 'Welding', 'Area Fabrikasi', 'Baik'),
            ('Mesin Bubut Konvensional', 'EMCO', 'Turning', 'Workshop A', 'Baik'),
            ('Pompa Sirkulasi', 'Grundfos', 'Utilitas', 'Ruang Utilitas', 'Baik'),
        ]
        assets = []
        for index, (name, brand, category, location, condition) in enumerate(names, 1):
            asset, created = Asset.objects.get_or_create(asset_uid=f'VM-DEMO-{index:04d}', defaults={
                'kode_asset': f'LEGACY-{(index + 1) // 2:03d}', 'nama_mesin': name, 'merk': brand,
                'kategori': category, 'lokasi': location, 'kondisi': condition,
                'status': 'Perbaikan' if condition == 'Rusak Berat' else 'Operasional',
                'serial_number': f'DEMO-SN-{index:04d}', 'tahun_perolehan': 2021 + index % 4,
                'sumber_data': 'DEMO tambahan, bukan SQL sumber', 'is_demo': True,
                'tanggal_pendataan': today, 'maintenance_anchor': today.replace(day=min(index * 3, 28)),
                'penanggung_jawab': 'Tim Workshop', 'kapasitas_spesifikasi': 'Data demonstrasi. Ganti dengan spesifikasi fisik mesin.',
            })
            if not asset.is_demo:
                raise CommandError('ID demo berbenturan dengan mesin operasional.')
            assets.append(asset)
        tasks = [
            ('Open', 1, tech1, 'Sedang', 'Preventif', 'Pemeriksaan pelumasan spindle dan kebersihan area kerja.', 1),
            ('Open', 2, tech2, 'Rendah', 'Preventif', 'Pemeriksaan kelistrikan dan uji fungsi panel kendali.', 2),
            ('Proses', 3, tech1, 'Darurat', 'Korektif', 'Tekanan udara turun. Periksa kebocoran pada jalur kompresor.', 0),
            ('Proses', 4, tech2, 'Sedang', 'Preventif', 'Kalibrasi putaran spindle dan inspeksi chuck bor.', 0),
            ('Review', 5, tech1, 'Tinggi', 'Korektif', 'Getaran pada meja gerinda. Periksa dudukan dan bearing.', -1),
            ('Revisi', 6, tech2, 'Tinggi', 'Korektif', 'Arus pengelasan tidak stabil. Periksa sambungan dan regulator.', -1),
            ('Selesai', 7, tech1, 'Sedang', 'Preventif', 'Penggantian oli gearbox dan pemeriksaan sabuk penggerak.', -3),
            ('Selesai', 8, tech2, 'Rendah', 'Preventif', 'Pembersihan filter dan uji aliran pompa.', -4),
        ]
        proof = io.BytesIO()
        picture = Image.new('RGB', (720, 400), '#262b3b')
        ImageDraw.Draw(picture).text((55, 170), 'DEMO EVIDENCE / NOT A REAL MACHINE PHOTO', fill='#d1c2fc', font_size=24)
        picture.save(proof, format='PNG')
        for index, (status, asset_index, tech, priority, kind, instruction, offset) in enumerate(tasks, 1):
            ticket, created = WorkOrder.objects.get_or_create(wo_number=f'WO-DEMO-{index:04d}', defaults={
                'asset': assets[asset_index - 1], 'status': status, 'assigned_to': tech, 'teknisi': tech.get_full_name(),
                'prioritas': priority, 'jenis': kind, 'severity': assets[asset_index - 1].kondisi,
                'keluhan_gejala': instruction, 'scheduled_date': today + timedelta(days=offset),
                'confirmed': True, 'created_by': manager, 'pelapor': 'DEMO',
                'mulai_pekerjaan': timezone.now() - timedelta(hours=3) if status != 'Open' else None,
                'selesai_pekerjaan': timezone.now() - timedelta(hours=1) if status == 'Selesai' else None,
            })
            if not created:
                continue
            TicketEvent.objects.create(ticket=ticket, actor=manager, action='Tiket demo dibuat', notes='Contoh alur kerja; bukan data lapangan.')
            if status in ['Review', 'Revisi', 'Selesai']:
                report = MaintenanceReport.objects.create(ticket=ticket, author=tech,
                    kondisi_sebelum='DEMO: ditemukan kotoran dan komponen perlu diperiksa.',
                    kondisi_sesudah='DEMO: komponen dibersihkan, dikencangkan, dan diuji fungsi.',
                    resulting_condition='Baik', submitted_at=timezone.now(),
                    manager_notes='Lengkapi pemeriksaan kestabilan saat beban penuh.' if status == 'Revisi' else '')
                card = ActionCard.objects.create(report=report, komponen='Komponen utama (demo)',
                    detail_kerusakan='DEMO: kondisi komponen memerlukan pembersihan dan penyetelan.',
                    tindakan_perbaikan='DEMO: pembersihan, penyetelan, dan pengujian fungsi.')
                for stage in ['before', 'after', 'damage', 'repair']:
                    Attachment.objects.create(report=report, card=card if stage in ['damage', 'repair'] else None,
                        stage=stage, file=ContentFile(proof.getvalue(), name=f'demo-{index}-{stage}.png'),
                        original_name=f'DEMO-{stage}.png', content_type='image/png')
                TicketEvent.objects.create(ticket=ticket, actor=tech, action='Laporan demo tersimpan', snapshot=report_snapshot(report))
        KPI.objects.get_or_create(asset=assets[0], periode='DEMO-Before', defaults={'operating_time_jam': 160, 'failure': 4, 'repair_time_jam': 12, 'downtime_jam': 16, 'pm_terjadwal': 4, 'pm_terlaksana': 2})
        KPI.objects.get_or_create(asset=assets[0], periode='DEMO-After', defaults={'operating_time_jam': 176, 'failure': 2, 'repair_time_jam': 4, 'downtime_jam': 6, 'pm_terjadwal': 4, 'pm_terlaksana': 4})
        InitialCondition.objects.get_or_create(asset=assets[0], komponen_item='Spindle (DEMO)', defaults={'tanggal': today, 'kondisi_aktual': 'Perlu pelumasan', 'ok_ng': 'NG', 'petugas': tech1.get_full_name()})
        FailureHistory.objects.get_or_create(failure_id='FAIL-DEMO-001', defaults={'asset': assets[0], 'tanggal_jam_mulai': timezone.now() - timedelta(days=5),
            'komponen': 'Spindle (DEMO)', 'gejala': 'Bunyi gesekan saat berputar', 'tindakan_perbaikan': 'Pelumasan ulang', 'downtime_jam': 2, 'sumber_data': 'DEMO'})
        Downtime.objects.get_or_create(downtime_id='DT-DEMO-001', defaults={'asset': assets[0], 'tanggal': today - timedelta(days=5), 'durasi_jam': 2, 'penyebab': 'Pelumasan spindle (DEMO)', 'jenis': 'Planned'})
        self.stdout.write(self.style.SUCCESS('Demo siap: manager / teknisi / teknisi2. Password akun baru sesuai --password; password akun lama tidak diubah.'))
