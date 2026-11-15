import csv
import io
from datetime import date
import qrcode
import qrcode.image.svg
from django import forms
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .access import is_manager, manager_required, visible_tickets
from .forms import AssetForm, WorkOrderForm, ReportForm, CardFormSet, ReviewForm, StyledForm
from .models import (Asset, WorkOrder, MaintenanceReport, Attachment, TicketEvent, FailureHistory,
                     Downtime, KPI, IndicatorFormula, SourceArchive, PMSchedule)
from .services import generate_monthly, start_ticket, review_ticket, add_attachment, report_snapshot


def page(request, queryset, size=20):
    return Paginator(queryset, size).get_page(request.GET.get('page'))


@login_required
def dashboard(request):
    tickets = visible_tickets(request.user)
    active = tickets.exclude(status__in=['Selesai', 'Batal'])
    counts = dict(tickets.values('status').annotate(total=Count('pk')).values_list('status', 'total'))
    lanes = [{'status': status, 'count': counts.get(status, 0), 'tickets': tickets.filter(status=status)[:8]} for status in ['Open', 'Proses', 'Review', 'Revisi', 'Selesai']]
    context = {'title': 'Dashboard', 'active_nav': 'dashboard', 'today': timezone.localdate(),
               'asset_count': Asset.objects.exclude(status='Afkir').count(), 'active_count': active.count(),
               'done_count': counts.get('Selesai', 0), 'overdue_count': active.filter(scheduled_date__lt=timezone.localdate()).count(),
               'lanes': lanes, 'upcoming': active.order_by('scheduled_date')[:5],
               'priorities': [{'name': p, 'count': active.filter(prioritas=p).count()} for p, _ in WorkOrder.PRIORITIES],
               'conditions': Asset.objects.values('kondisi').annotate(total=Count('pk')),
               'recent_events': TicketEvent.objects.filter(ticket__in=tickets).select_related('actor', 'ticket')[:5]}
    return render(request, 'maintenance/dashboard.html', context)


@login_required
def asset_list(request):
    assets = Asset.objects.all()
    query = request.GET.get('q', '').strip()
    if query:
        assets = assets.filter(Q(nama_mesin__icontains=query) | Q(asset_uid__icontains=query) | Q(kode_asset__icontains=query) | Q(serial_number__icontains=query) | Q(lokasi__icontains=query))
    if request.GET.get('status'):
        assets = assets.filter(status=request.GET['status'])
    return render(request, 'maintenance/assets.html', {'title': 'Master mesin', 'active_nav': 'assets', 'page_obj': page(request, assets), 'statuses': Asset.STATUS})


@login_required
def asset_detail(request, uid):
    asset = get_object_or_404(Asset, asset_uid=uid)
    tickets = visible_tickets(request.user).filter(asset=asset)
    return render(request, 'maintenance/asset_detail.html', {'title': asset.nama_mesin, 'active_nav': 'assets', 'asset': asset,
                  'tickets': tickets, 'fields': [(f.verbose_name.replace('_', ' ').capitalize(), f.value_from_object(asset)) for f in Asset._meta.fields if f.name not in ['gambar', 'id_asset', 'is_demo']]})


@manager_required
def asset_edit(request, uid=None):
    asset = get_object_or_404(Asset, asset_uid=uid) if uid else None
    form = AssetForm(request.POST or None, request.FILES or None, instance=asset)
    if request.method == 'POST' and form.is_valid():
        asset = form.save()
        messages.success(request, 'Data mesin tersimpan. ID unik dan riwayat tetap dipertahankan.')
        return redirect('asset_detail', uid=asset.asset_uid)
    return render(request, 'maintenance/form.html', {'title': 'Edit mesin' if asset else 'Tambah mesin', 'form': form, 'active_nav': 'assets'})


@manager_required
@require_POST
def asset_retire(request, uid):
    asset = get_object_or_404(Asset, asset_uid=uid)
    asset.status = 'Afkir'
    asset.save(update_fields=['status'])
    messages.success(request, 'Mesin dinonaktifkan. Seluruh riwayat tetap tersimpan; tiket yang masih terbuka dapat diselesaikan atau dibatalkan Manager.')
    return redirect('asset_detail', uid=uid)


@login_required
def asset_qr(request, uid):
    asset = get_object_or_404(Asset, asset_uid=uid)
    url = request.build_absolute_uri(reverse('asset_detail', args=[asset.asset_uid]))
    output = io.BytesIO()
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).save(output)
    return HttpResponse(output.getvalue(), content_type='image/svg+xml')


@login_required
def asset_image(request, uid):
    asset = get_object_or_404(Asset, asset_uid=uid)
    if not asset.gambar:
        raise Http404
    return FileResponse(asset.gambar.open('rb'))


@login_required
def ticket_list(request):
    tickets = visible_tickets(request.user)
    query = request.GET.get('q', '').strip()
    if query:
        tickets = tickets.filter(Q(wo_number__icontains=query) | Q(asset__nama_mesin__icontains=query) | Q(assigned_to__username__icontains=query))
    for field in ['status', 'prioritas']:
        if request.GET.get(field):
            tickets = tickets.filter(**{field: request.GET[field]})
    return render(request, 'maintenance/tickets.html', {'title': 'Work order', 'active_nav': 'tickets', 'page_obj': page(request, tickets),
                                                       'statuses': WorkOrder.STATUSES, 'priorities': WorkOrder.PRIORITIES})


@manager_required
def ticket_edit(request, pk=None):
    ticket = get_object_or_404(WorkOrder, pk=pk) if pk else None
    if ticket and ticket.status not in ['Open', 'Revisi']:
        messages.error(request, 'Penugasan hanya dapat diubah pada tiket Open atau Revisi.')
        return redirect('ticket_detail', pk=pk)
    form = WorkOrderForm(request.POST or None, instance=ticket)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                if ticket:
                    current = WorkOrder.objects.select_for_update().get(pk=pk)
                    if current.status not in ['Open', 'Revisi']:
                        raise PermissionDenied('Status tiket telah berubah.')
                result = form.save(commit=False)
                if not ticket:
                    result.created_by = request.user
                    result.pelapor = request.user.get_full_name() or request.user.username
                result.teknisi = (result.assigned_to.get_full_name() or result.assigned_to.username) if result.assigned_to else None
                result.save()
                PMSchedule.objects.filter(work_order=result).update(tanggal_terjadwal=result.scheduled_date, petugas=result.teknisi)
                TicketEvent.objects.create(ticket=result, actor=request.user, action='Penugasan diperbarui' if ticket else 'Tiket dibuat',
                                           notes=f'{result.scheduled_date} · {result.teknisi or "Belum ditugaskan"} · {result.prioritas}')
        except IntegrityError:
            form.add_error(None, 'Jadwal berbenturan dengan perubahan terbaru. Pilih tanggal / teknisi lain dan coba lagi.')
        else:
            messages.success(request, 'Work order tersimpan.')
            return redirect('ticket_detail', pk=result.pk)
    return render(request, 'maintenance/form.html', {'title': 'Atur work order' if ticket else 'Buat work order', 'form': form, 'active_nav': 'tickets'})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    report = MaintenanceReport.objects.filter(ticket=ticket).prefetch_related('cards__attachments', 'attachments').first()
    return render(request, 'maintenance/ticket_detail.html', {'title': ticket.wo_number, 'active_nav': 'tickets', 'ticket': ticket, 'report': report,
                  'review_form': ReviewForm(), 'can_execute': ticket.assigned_to_id == request.user.pk and ticket.confirmed,
                  'general_attachments': report.attachments.filter(card__isnull=True) if report else [],
                  'events': ticket.events.select_related('actor')})


@login_required
@require_POST
def ticket_start(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    try:
        start_ticket(ticket, request.user)
        messages.success(request, 'Pekerjaan dimulai. Silakan isi laporan maintenance.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('ticket_detail', pk=pk)


@manager_required
@require_POST
def ticket_cancel(request, pk):
    ticket = get_object_or_404(WorkOrder, pk=pk)
    notes = request.POST.get('notes', '').strip()
    with transaction.atomic():
        if not notes or not WorkOrder.objects.filter(pk=pk, status__in=['Open', 'Revisi']).update(status='Batal'):
            messages.error(request, 'Pembatalan membutuhkan alasan dan hanya diizinkan pada tiket Open / Revisi.')
        else:
            PMSchedule.objects.filter(work_order=ticket).update(status='Batal')
            TicketEvent.objects.create(ticket=ticket, actor=request.user, action='Tiket dibatalkan', notes=notes)
            messages.success(request, 'Tiket dibatalkan; data dan lampiran tetap tersimpan.')
    return redirect('ticket_detail', pk=pk)


@login_required
def report_edit(request, pk):
    ticket = get_object_or_404(WorkOrder, pk=pk, assigned_to=request.user)
    if not ticket.confirmed or ticket.status not in ['Proses', 'Revisi']:
        raise PermissionDenied('Laporan hanya dapat diisi oleh teknisi yang ditugaskan saat Proses / Revisi.')
    report = MaintenanceReport.objects.filter(ticket=ticket).first() or MaintenanceReport(ticket=ticket, author=request.user)
    form = ReportForm(request.POST or None, request.FILES or None, instance=report)
    formset = CardFormSet(request.POST or None, request.FILES or None, instance=report, prefix='cards')
    if request.method == 'POST':
        valid = form.is_valid()
        cards_valid = formset.is_valid()
        if valid and cards_valid:
            for field, stage in [('before_file', 'before'), ('after_file', 'after')]:
                if not form.cleaned_data.get(field) and not (report.pk and report.attachments.filter(stage=stage, card__isnull=True).exists()):
                    form.add_error(field, 'Lampiran bukti wajib disertakan sebelum mengirim laporan.')
            for card_form in formset:
                if not card_form.cleaned_data:
                    continue
                for field, stage in [('damage_file', 'damage'), ('repair_file', 'repair')]:
                    if not card_form.cleaned_data.get(field) and not (card_form.instance.pk and card_form.instance.attachments.filter(stage=stage).exists()):
                        card_form.add_error(field, 'Bukti wajib dilampirkan untuk kartu ini.')
            if form.is_valid() and all(not cf.errors for cf in formset):
                with transaction.atomic():
                    if not WorkOrder.objects.filter(pk=pk, assigned_to=request.user, confirmed=True, status__in=['Proses', 'Revisi']).update(status='Review'):
                        raise PermissionDenied('Status tiket berubah; laporan tidak disimpan.')
                    report = form.save(commit=False)
                    report.author = request.user
                    report.submitted_at = timezone.now()
                    report.save()
                    for field, stage in [('before_file', 'before'), ('after_file', 'after')]:
                        add_attachment(report, None, stage, form.cleaned_data.get(field))
                    for card_form in formset:
                        if not card_form.cleaned_data:
                            continue
                        card = card_form.save(commit=False)
                        card.report = report
                        card.save()
                        for field, stage in [('damage_file', 'damage'), ('repair_file', 'repair')]:
                            add_attachment(report, card, stage, card_form.cleaned_data.get(field))
                    TicketEvent.objects.create(ticket=ticket, actor=request.user, action='Laporan dikirim untuk review', snapshot=report_snapshot(report))
                messages.success(request, 'Laporan terkirim. Manager dapat meninjau seluruh kartu dan bukti.')
                return redirect('ticket_detail', pk=pk)
    return render(request, 'maintenance/report_form.html', {'title': 'Laporan maintenance', 'active_nav': 'tickets', 'ticket': ticket,
                                                           'form': form, 'formset': formset, 'report': report})


@manager_required
@require_POST
def ticket_review(request, pk):
    ticket = get_object_or_404(WorkOrder, pk=pk)
    form = ReviewForm(request.POST)
    if form.is_valid() and MaintenanceReport.objects.filter(ticket=ticket).exists():
        try:
            review_ticket(ticket, request.user, form.cleaned_data['decision'], form.cleaned_data['notes'])
            messages.success(request, 'Keputusan review tersimpan.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    else:
        messages.error(request, 'Review gagal. Laporan harus tersedia dan revisi wajib memiliki catatan.')
    return redirect('ticket_detail', pk=pk)


@login_required
def attachment(request, pk):
    evidence = get_object_or_404(Attachment.objects.select_related('report__ticket'), pk=pk)
    if not is_manager(request.user) and evidence.report.ticket.assigned_to_id != request.user.pk:
        raise PermissionDenied
    response = FileResponse(evidence.file.open('rb'), content_type=evidence.content_type, filename=evidence.original_name)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def schedule(request):
    month = request.GET.get('month', timezone.localdate().strftime('%Y-%m'))
    try:
        target = date.fromisoformat(month + '-01')
    except ValueError:
        target = timezone.localdate().replace(day=1)
        month = target.strftime('%Y-%m')
    tickets = visible_tickets(request.user).filter(scheduled_date__year=target.year, scheduled_date__month=target.month)
    return render(request, 'maintenance/schedule.html', {'title': 'Jadwal maintenance', 'active_nav': 'schedule', 'month': month,
                                                        'page_obj': page(request, tickets, 50)})


@manager_required
@require_POST
def generate_schedule(request):
    try:
        target = date.fromisoformat(request.POST.get('month', '') + '-01')
        count = generate_monthly(target)
        messages.success(request, f'{count} tiket bulanan dibuat. Jadwal yang sudah ada tidak digandakan.')
    except ValueError:
        messages.error(request, 'Bulan tidak valid.')
    return redirect('schedule')


@manager_required
def analytics(request):
    return render(request, 'maintenance/analytics.html', {'title': 'Statistik & KPI', 'active_nav': 'analytics',
        'kpis': KPI.objects.select_related('asset').all(), 'formulas': IndicatorFormula.objects.all(),
        'failure_count': FailureHistory.objects.count(), 'downtime': Downtime.objects.aggregate(total=Sum('durasi_jam'))['total'] or 0,
        'completed': WorkOrder.objects.filter(status='Selesai').count(),
        'conditions': Asset.objects.values('kondisi').annotate(total=Count('pk'))})


SOURCE_TABLES = ['master_asset', 'kondisi_awal', 'work_order', 'histori_kerusakan', 'pm_schedule', 'downtime', 'kpi_before_after',
                 'user_requirement', 'blackbox', 'uat', 'sus', 'logbook_realisasi', 'checklist_bukti', 'rumus_indikator']


def source_model(table):
    if table not in SOURCE_TABLES:
        raise Http404
    return next(m for m in apps.get_app_config('maintenance').get_models() if m._meta.db_table == table)


@manager_required
def source_data(request, table=None):
    models = [source_model(t) for t in SOURCE_TABLES]
    context = {'title': 'Data & arsip', 'active_nav': 'data', 'tables': [{'name': m._meta.db_table, 'count': m.objects.count()} for m in models],
               'archives': SourceArchive.objects.all(), 'selected_table': table}
    if table:
        model = source_model(table)
        fields = model._meta.fields
        objects = page(request, model.objects.order_by(model._meta.pk.name))
        context.update({'headers': [f.column for f in fields], 'rows': [[getattr(obj, f.attname) for f in fields] for obj in objects], 'page_obj': objects})
    return render(request, 'maintenance/source_data.html', context)


@manager_required
def source_add(request, table):
    model = source_model(table)
    if table == 'master_asset':
        return redirect('asset_create')
    if table == 'work_order':
        return redirect('ticket_create')
    Form = forms.modelform_factory(model, form=type('SourceForm', (StyledForm, forms.ModelForm), {}), fields='__all__')
    form = Form(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Data tambahan tersimpan.')
        return redirect('source_table', table=table)
    return render(request, 'maintenance/form.html', {'title': f'Tambah data · {table}', 'form': form, 'active_nav': 'data'})


@manager_required
def export_table(request, table):
    model = source_model(table)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{table}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    fields = model._meta.fields
    writer.writerow([field.column for field in fields])
    for obj in model.objects.order_by(model._meta.pk.name).iterator():
        values = [getattr(obj, field.attname) for field in fields]
        # Prevent spreadsheet formulas from running on opening user-entered text.
        writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in values])
    return response


@manager_required
def download_source(request, pk):
    archive = get_object_or_404(SourceArchive, pk=pk)
    response = HttpResponse(bytes(archive.content), content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="Main_data-original.sql"'
    return response
