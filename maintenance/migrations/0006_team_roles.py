from django.apps import apps as installed_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations


def create_team_roles(apps, schema_editor):
    using = schema_editor.connection.alias
    groups = apps.get_model('auth', 'Group').objects.using(using)
    groups.get_or_create(name='Teknisi')
    manager, created = groups.get_or_create(name='Manager')
    if created:
        # On a fresh database, Django normally creates permissions after migrations.
        create_permissions(installed_apps.get_app_config('maintenance'), apps=apps, using=using, verbosity=0)
        permissions = apps.get_model('auth', 'Permission').objects.using(using).filter(
            content_type__app_label='maintenance',
        )
        manager.permissions.add(*permissions.exclude(codename__startswith='delete_'))


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('maintenance', '0005_asset_deletion_and_report_photo_removal'),
    ]

    operations = [migrations.RunPython(create_team_roles, migrations.RunPython.noop)]
