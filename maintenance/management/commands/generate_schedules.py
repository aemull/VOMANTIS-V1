from datetime import date
from django.core.management.base import BaseCommand, CommandError
from maintenance.services import generate_monthly


class Command(BaseCommand):
    help = 'Buat tiket maintenance bulanan secara idempoten. Jalankan setiap hari dengan Task Scheduler/cron.'

    def add_arguments(self, parser):
        parser.add_argument('--month', help='Bulan YYYY-MM; default bulan saat ini (Asia/Jakarta).')

    def handle(self, *args, **options):
        try:
            target = date.fromisoformat(options['month'] + '-01') if options['month'] else None
        except ValueError as exc:
            raise CommandError('Gunakan format YYYY-MM.') from exc
        self.stdout.write(self.style.SUCCESS(f'{generate_monthly(target)} tiket bulanan baru dibuat.'))
