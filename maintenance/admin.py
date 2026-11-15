from django.apps import apps
from django.contrib import admin
from .models import Asset, WorkOrder, MaintenanceReport, ActionCard, Attachment, TicketEvent, SourceArchive, SourceRecord


class PreserveDataAdmin(admin.ModelAdmin):
    """Historical records are never physically deleted through the admin."""
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Asset)
class AssetAdmin(PreserveDataAdmin):
    list_display = ['asset_uid', 'nama_mesin', 'kode_asset', 'serial_number', 'status', 'kondisi']
    search_fields = ['asset_uid', 'nama_mesin', 'kode_asset', 'serial_number']
    list_filter = ['status', 'kondisi', 'is_demo']
    readonly_fields = ['asset_uid']


class ReadOnlyAdmin(PreserveDataAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


for model in apps.get_app_config('maintenance').get_models():
    if model == Asset:
        continue
    if model in [WorkOrder, MaintenanceReport, ActionCard, Attachment, TicketEvent, SourceArchive, SourceRecord]:
        admin.site.register(model, ReadOnlyAdmin)
    else:
        admin.site.register(model, PreserveDataAdmin)

admin.site.site_header = 'VOMANTIS · Administrasi'
admin.site.site_title = 'VOMANTIS'
admin.site.index_title = 'Data maintenance'
