from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from maintenance.source_import import import_source, verify_archive


class Command(BaseCommand):
    help = 'Impor seluruh tabel dan data SQL sumber tanpa menghapus atau menimpa data.'

    def add_arguments(self, parser):
        parser.add_argument('path', nargs='?', default=str(settings.BASE_DIR / 'Main_data.sql'))

    def handle(self, *args, **options):
        try:
            archive, created = import_source(options['path'])
            tables, rows = verify_archive(archive)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'{"Diimpor" if created else "Sudah diimpor"}: {tables} tabel, {rows} baris. SHA256 {archive.sha256}'))
        for table, count in archive.summary['counts'].items():
            self.stdout.write(f'  {table}: {count}')
