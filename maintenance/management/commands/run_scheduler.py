import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from maintenance.services import generate_monthly


class Command(BaseCommand):
    help = 'Jalankan penjadwal bulanan lokal sampai dihentikan; default cek setiap 1 jam.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=3600, help='Jeda pemeriksaan dalam detik, minimal 60.')
        parser.add_argument('--once', action='store_true', help='Satu kali pemeriksaan lalu keluar.')

    def handle(self, *args, **options):
        if options['interval'] < 60:
            raise CommandError('Interval minimal 60 detik.')
        self.stdout.write('Penjadwal VOMANTIS aktif (Asia/Jakarta). Ctrl+C untuk berhenti.')
        try:
            while True:
                close_old_connections()
                count = generate_monthly()
                self.stdout.write(f'{count} tiket bulanan baru dibuat.')
                if options['once']:
                    return
                time.sleep(options['interval'])
        except KeyboardInterrupt:
            self.stdout.write('Penjadwal dihentikan.')
