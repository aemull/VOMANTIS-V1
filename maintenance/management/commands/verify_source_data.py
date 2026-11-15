from django.core.management.base import BaseCommand, CommandError
from maintenance.models import SourceArchive
from maintenance.source_import import verify_archive


class Command(BaseCommand):
    help = 'Verifikasi checksum, pemetaan semua kolom, snapshot, serta keberadaan setiap baris impor.'

    def handle(self, *args, **options):
        if not SourceArchive.objects.exists():
            raise CommandError('Belum ada arsip. Jalankan import_main_data.')
        for archive in SourceArchive.objects.all():
            try:
                tables, rows = verify_archive(archive)
            except Exception as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(self.style.SUCCESS(f'OK {archive.filename}: {tables} tabel, {rows} baris; checksum dan snapshot cocok.'))
