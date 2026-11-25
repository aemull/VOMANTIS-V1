from pathlib import Path
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from PIL import Image
from .access import technicians
from .models import Asset, WorkOrder, MaintenanceReport, ActionCard, Attachment


def validate_evidence(file):
    if file.size > 25 * 1024 * 1024:
        raise ValidationError('Ukuran setiap lampiran maksimal 25 MB.')
    suffix = Path(file.name).suffix.lower()
    header = file.read(32)
    file.seek(0)
    if suffix in ['.jpg', '.jpeg', '.png', '.webp']:
        try:
            with Image.open(file) as picture:
                picture.verify()
            file.seek(0)
        except Exception as exc:
            raise ValidationError('Foto tidak valid. Gunakan JPG, PNG, atau WebP.') from exc
        file.content_type = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}[suffix]
    elif suffix == '.mp4' and header[4:8] == b'ftyp':
        file.content_type = 'video/mp4'
    elif suffix == '.webm' and header[:4] == b'\x1aE\xdf\xa3':
        file.content_type = 'video/webm'
    else:
        raise ValidationError('Gunakan foto JPG/PNG/WebP atau video MP4/WebM yang valid.')
    return file


class StyledForm:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 3
            if isinstance(field, forms.DateField) and not isinstance(field, forms.DateTimeField):
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'})


class TeamAccountForm(StyledForm, UserCreationForm):
    first_name = forms.CharField(label='Nama lengkap', max_length=100)
    role = forms.ChoiceField(label='Peran', choices=[('Teknisi', 'Teknisi'), ('Manager', 'Manager')])
    field_order = ['first_name', 'username', 'role', 'password1', 'password2']

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ['username', 'first_name']


class MultipleImageInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            super().clean(None, initial)
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > 10:
            raise ValidationError('Pilih maksimal 10 foto dalam satu unggahan.')
        if sum(file.size for file in files) > 100 * 1024 * 1024:
            raise ValidationError('Total ukuran foto maksimal 100 MB per unggahan.')
        cleaned = []
        for file in files:
            if Path(file.name).suffix.lower() not in ['.jpg', '.jpeg', '.png', '.webp']:
                raise ValidationError('Foto mesin harus berupa JPG, PNG, atau WebP.')
            cleaned.append(super().clean(file, initial))
            validate_evidence(cleaned[-1])
        return cleaned


class AssetPhotoForm(StyledForm, forms.Form):
    photos = MultipleImageField(label='Tambah foto mesin', help_text='JPG, PNG, WebP. Maksimal 10 foto sekaligus, 25 MB per foto, total 100 MB.',
                               widget=MultipleImageInput(attrs={'accept': '.jpg,.jpeg,.png,.webp'}))


class AssetForm(StyledForm, forms.ModelForm):
    photos = MultipleImageField(label='Foto galeri tambahan', required=False,
                               help_text='Pilih beberapa foto sekaligus. Maksimal 10 foto, 25 MB per foto, total 100 MB.',
                               widget=MultipleImageInput(attrs={'accept': '.jpg,.jpeg,.png,.webp'}))

    class Meta:
        model = Asset
        exclude = ['asset_uid', 'is_demo']
        labels = {'gambar': 'Foto utama'}
        help_texts = {'gambar': 'Ditampilkan pada kartu mesin. Foto tambahan dapat diunggah ke galeri.'}

    def clean_serial_number(self):
        return self.cleaned_data.get('serial_number') or None

    def clean_gambar(self):
        picture = self.cleaned_data.get('gambar')
        if picture and hasattr(picture, 'content_type'):
            validate_evidence(picture)
        return picture


class WorkOrderForm(StyledForm, forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ['asset', 'jenis', 'prioritas', 'severity', 'scheduled_date', 'assigned_to', 'confirmed', 'keluhan_gejala', 'spare_part', 'biaya']
        labels = {'asset': 'Mesin', 'assigned_to': 'Teknisi yang ditugaskan', 'keluhan_gejala': 'Keluhan / instruksi kerja',
                  'confirmed': 'Setujui jadwal dan penugasan'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assets = Asset.objects.in_master().exclude(status='Afkir')
        if self.instance.asset_id:
            assets = assets | Asset.objects.filter(pk=self.instance.asset_id)
        self.fields['asset'].queryset = assets
        self.fields['assigned_to'].queryset = technicians()
        self.fields['keluhan_gejala'].required = True

    def clean(self):
        data = super().clean()
        if data.get('confirmed') and not data.get('assigned_to'):
            self.add_error('assigned_to', 'Pilih teknisi sebelum mengonfirmasi jadwal.')
        # MVP reserves one confirmed task per technician per day; no silent overlaps.
        if data.get('confirmed') and data.get('assigned_to') and data.get('scheduled_date'):
            collision = WorkOrder.objects.filter(assigned_to=data['assigned_to'], scheduled_date=data['scheduled_date'], confirmed=True).exclude(status__in=['Selesai', 'Batal'])
            if self.instance.pk:
                collision = collision.exclude(pk=self.instance.pk)
            if collision.exists():
                self.add_error('scheduled_date', 'Teknisi memiliki tugas terkonfirmasi pada tanggal ini. Pilih hari atau teknisi lain.')
        return data


class ReportForm(StyledForm, forms.ModelForm):
    before_file = forms.FileField(label='Foto / video kondisi sebelum', required=False, validators=[validate_evidence])
    after_file = forms.FileField(label='Foto / video kondisi sesudah', required=False, validators=[validate_evidence])
    remove_photos = forms.ModelMultipleChoiceField(queryset=Attachment.objects.none(), required=False,
                                                 error_messages={'invalid_choice': 'Foto yang dipilih sudah dihapus atau tidak tersedia di laporan ini.'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['remove_photos'].queryset = self.instance.attachments.filter(
                removed_at__isnull=True, content_type__startswith='image/')

    class Meta:
        model = MaintenanceReport
        fields = ['kondisi_sebelum', 'kondisi_sesudah', 'resulting_condition']


class CardForm(StyledForm, forms.ModelForm):
    damage_file = forms.FileField(label='Foto / video kerusakan', required=False, validators=[validate_evidence])
    repair_file = forms.FileField(label='Foto / video perbaikan', required=False, validators=[validate_evidence])

    class Meta:
        model = ActionCard
        fields = ['komponen', 'detail_kerusakan', 'tindakan_perbaikan']


CardFormSet = inlineformset_factory(MaintenanceReport, ActionCard, form=CardForm, extra=0, min_num=1, validate_min=True, max_num=20, validate_max=True, can_delete=False)


class ReviewForm(StyledForm, forms.Form):
    decision = forms.ChoiceField(label='Keputusan', choices=[('approve', 'Setujui & selesaikan'), ('reject', 'Kembalikan untuk revisi')])
    notes = forms.CharField(label='Catatan Manager', widget=forms.Textarea, required=False)
    submission = forms.CharField(widget=forms.HiddenInput, required=False)

    def clean(self):
        data = super().clean()
        if data.get('decision') == 'reject' and not data.get('notes', '').strip():
            self.add_error('notes', 'Catatan wajib diisi saat meminta revisi.')
        return data
