import getpass
import os
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Buat satu akun admin tanpa data contoh; akun yang sudah ada tidak diubah.'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Default: DJANGO_SUPERUSER_USERNAME atau admin.')
        parser.add_argument('--email', help='Default: DJANGO_SUPERUSER_EMAIL atau kosong.')
        parser.add_argument('--noinput', action='store_true', help='Baca password dari DJANGO_SUPERUSER_PASSWORD.')

    def existing_admin(self, user):
        if not (user.is_superuser and user.is_staff and user.is_active):
            raise CommandError('Username sudah dipakai akun non-admin atau nonaktif. Pilih username lain; akun lama tidak diubah.')
        self.stdout.write(f'Admin {user.username} sudah ada; password dan profil tetap.')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username'] or os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = options['email'] if options['email'] is not None else os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
        existing = User.objects.filter(username=username).first()
        if existing is not None:
            self.existing_admin(existing)
            return

        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not password:
            if options['noinput'] or not sys.stdin.isatty():
                raise CommandError('Set DJANGO_SUPERUSER_PASSWORD atau jalankan seed_admin di terminal interaktif.')
            self.stdout.write(f'Membuat admin: {username}')
            try:
                password = getpass.getpass('Password admin: ')
                confirmation = getpass.getpass('Ulangi password admin: ')
            except (EOFError, KeyboardInterrupt):
                raise CommandError('Pembuatan admin dibatalkan.') from None
            if password != confirmation:
                raise CommandError('Password tidak cocok; akun belum dibuat.')

        user = User(username=username, email=email, is_superuser=True, is_staff=True, is_active=True)
        try:
            validate_password(password, user)
            user.set_password(password)
            user.full_clean(validate_unique=False)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc

        # get_or_create also protects against concurrent setup runs. Never reset
        # a password or promote an existing account on a username collision.
        admin, created = User.objects.get_or_create(username=username, defaults={
            'email': email, 'password': user.password,
            'is_superuser': True, 'is_staff': True, 'is_active': True,
        })
        if not created:
            self.existing_admin(admin)
            return
        self.stdout.write(self.style.SUCCESS(f'Admin {admin.username} siap. Tidak ada data contoh yang dibuat.'))
