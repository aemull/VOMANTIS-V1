from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Siapkan grup Manager dan Teknisi tanpa membuat akun atau data contoh.'

    def handle(self, *args, **options):
        manager, _ = Group.objects.get_or_create(name='Manager')
        Group.objects.get_or_create(name='Teknisi')
        permissions = Permission.objects.filter(content_type__app_label='maintenance').exclude(codename__startswith='delete_')
        manager.permissions.add(*permissions)
        self.stdout.write(self.style.SUCCESS('Grup Manager dan Teknisi siap.'))
