import calendar
import uuid
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Asset, WorkOrder, PMSchedule, TicketEvent, Attachment


@transaction.atomic
def generate_monthly(target=None):
    """One preventive ticket per active asset and calendar month; safe to rerun."""
    target = target or timezone.localdate()
    created = 0
    for asset in Asset.objects.exclude(status='Afkir').filter(maintenance_anchor__lte=date(target.year, target.month, calendar.monthrange(target.year, target.month)[1])):
        scheduled = date(target.year, target.month, min(asset.maintenance_anchor.day, calendar.monthrange(target.year, target.month)[1]))
        key = f'{asset.pk}:{target:%Y-%m}'
        ticket, new = WorkOrder.objects.get_or_create(monthly_key=key, defaults={
            'asset': asset, 'jenis': 'Preventif', 'prioritas': 'Sedang', 'severity': asset.kondisi,
            'scheduled_date': scheduled, 'keluhan_gejala': 'Pemeriksaan, pembersihan, pelumasan, dan uji fungsi rutin bulanan.',
            'pelapor': 'Penjadwal otomatis',
        })
        if new:
            PMSchedule.objects.create(pm_id='PM-' + uuid.uuid4().hex[:20].upper(), asset=asset,
                                      item_pm='Maintenance rutin bulanan', aktivitas=ticket.keluhan_gejala,
                                      interval='1 bulan', tanggal_terjadwal=scheduled, work_order=ticket)
            TicketEvent.objects.create(ticket=ticket, action='Jadwal bulanan dibuat', notes='Menunggu konfirmasi dan penugasan Manager.')
            created += 1
    return created


def add_attachment(report, card, stage, upload):
    if upload:
        Attachment.objects.create(report=report, card=card, stage=stage, file=upload,
                                  original_name=upload.name[:255], content_type=upload.content_type)


def report_snapshot(report):
    return {'kondisi_sebelum': report.kondisi_sebelum, 'kondisi_sesudah': report.kondisi_sesudah,
            'resulting_condition': report.resulting_condition,
            'cards': list(report.cards.values('id', 'komponen', 'detail_kerusakan', 'tindakan_perbaikan')),
            'attachment_ids': list(report.attachments.values_list('pk', flat=True))}


@transaction.atomic
def start_ticket(ticket, actor):
    if ticket.assigned_to_id != actor.pk or not ticket.confirmed:
        raise ValidationError('Tiket harus ditugaskan kepada Anda dan dikonfirmasi Manager.')
    changed = WorkOrder.objects.filter(pk=ticket.pk, status='Open', assigned_to=actor, confirmed=True).update(status='Proses', mulai_pekerjaan=timezone.now())
    if not changed:
        raise ValidationError('Status tiket sudah berubah. Muat ulang halaman.')
    TicketEvent.objects.create(ticket=ticket, actor=actor, action='Pekerjaan dimulai')


@transaction.atomic
def review_ticket(ticket, actor, decision, notes):
    report = ticket.report
    new_status = 'Selesai' if decision == 'approve' else 'Revisi'
    changed = WorkOrder.objects.filter(pk=ticket.pk, status='Review').update(status=new_status)
    if not changed:
        raise ValidationError('Laporan sudah ditinjau atau belum dikirim.')
    report.manager_notes = notes
    report.save(update_fields=['manager_notes'])
    if decision == 'approve':
        now = timezone.now()
        WorkOrder.objects.filter(pk=ticket.pk).update(selesai_pekerjaan=now, verifikasi=actor.get_full_name() or actor.username,
                                                     tindakan='\n'.join(report.cards.values_list('tindakan_perbaikan', flat=True)))
        # A retired asset stays retired even when its remaining work is reviewed.
        Asset.objects.filter(pk=ticket.asset_id).exclude(status='Afkir').update(
            kondisi=report.resulting_condition,
            status='Operasional' if report.resulting_condition == 'Baik' else 'Perbaikan')
        PMSchedule.objects.filter(work_order=ticket).update(status='Terlaksana', tanggal_realisasi=timezone.localdate(),
                                                           hasil=report.kondisi_sesudah, petugas=report.author.get_full_name() or report.author.username)
    TicketEvent.objects.create(ticket=ticket, actor=actor, action='Laporan disetujui' if decision == 'approve' else 'Revisi diminta',
                               notes=notes, snapshot=report_snapshot(report))
