from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import VehicleType, VehicleFeature, Vehicle, VehicleEdit, VehicleJourney, Livery, JourneyCode


class VehicleTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'double_decker', 'coach')
    list_editable = list_display[1:]


class VehicleAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            'reg': forms.TextInput(attrs={'style': 'width: 8em'}),
            'fleet_number': forms.TextInput(attrs={'style': 'width: 4em'}),
            'operator': forms.TextInput(attrs={'style': 'width: 4em'}),
        }


class VehicleAdmin(admin.ModelAdmin):
    list_display = ('code', 'fleet_number', 'reg', 'operator', 'vehicle_type',
                    'get_flickr_link', 'last_seen', 'livery', 'colours', 'notes')
    list_filter = (
        ('source', admin.RelatedOnlyFieldListFilter),
        ('operator', admin.RelatedOnlyFieldListFilter),
        'vehicle_type',
    )
    list_select_related = ['operator', 'livery', 'vehicle_type', 'latest_location']
    list_editable = ('fleet_number', 'reg', 'operator', 'vehicle_type', 'livery', 'colours', 'notes')
    autocomplete_fields = ('vehicle_type', 'livery')
    raw_id_fields = ('operator', 'source')
    search_fields = ('code', 'fleet_number', 'reg')
    ordering = ('-id',)
    actions = ('copy_livery', 'copy_type')

    def copy_livery(self, request, queryset):
        livery = Livery.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(livery=livery)
        self.message_user(request, f'Copied {livery} to {count} vehicles.')

    def copy_type(self, request, queryset):
        vehicle_type = VehicleType.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(vehicle_type=vehicle_type)
        self.message_user(request, f'Copied {vehicle_type} to {count} vehicles.')

    def last_seen(self, obj):
        if obj.latest_location:
            return obj.latest_location.datetime

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', VehicleAdminForm)
        return super().get_changelist_form(request, **kwargs)


def vehicle(obj):
    url = reverse('admin:vehicles_vehicle_change', args=(obj.vehicle_id,))
    return mark_safe(f'<a href="{url}">{obj.vehicle}</a>')


def fleet_number(obj):
    return obj.get_diff('fleet_number')


def reg(obj):
    return obj.get_diff('reg')


def vehicle_type(obj):
    return obj.get_diff('vehicle_type')


def notes(obj):
    return obj.get_diff('notes')


class VehicleEditAdmin(admin.ModelAdmin):
    list_display = ['id', vehicle, fleet_number, reg, vehicle_type, 'current', 'suggested',
                    notes, 'flickr']
    list_select_related = ['vehicle__vehicle_type', 'vehicle__livery', 'vehicle__operator', 'livery']
    list_filter = [
        ('vehicle__operator', admin.RelatedOnlyFieldListFilter)
    ]
    raw_id_fields = ['vehicle', 'livery']
    actions = ['apply_edits']

    def apply_edits(self, request, queryset):
        for edit in queryset:
            ok = True
            vehicle = edit.vehicle
            if edit.fleet_number:
                vehicle.fleet_number = edit.fleet_number
            if edit.reg:
                vehicle.reg = edit.reg
            if edit.notes:
                vehicle.notes = edit.notes
            if edit.vehicle_type:
                try:
                    vehicle.vehicle_type = VehicleType.objects.get(name__iexact=edit.vehicle_type)
                except VehicleType.DoesNotExist:
                    ok = False
            if edit.livery_id:
                vehicle.livery_id = edit.livery_id
                vehicle.colours = ''
            elif edit.colours and edit.colours != 'Other':
                vehicle.colours = edit.colours
            vehicle.save()
            if ok:
                edit.delete()
        self.message_user(request, 'Applied edits.')

    def current(self, obj):
        if obj.vehicle.livery:
            return obj.vehicle.livery.preview()
        if obj.vehicle.colours:
            return Livery(colours=obj.vehicle.colours).preview()

    def suggested(self, obj):
        if obj.livery:
            return obj.livery.preview()
        if obj.colours:
            if obj.colours == 'Other':
                return obj.colours
            return Livery(colours=obj.colours).preview()

    def flickr(self, obj):
        return obj.vehicle.get_flickr_link()


class VehicleJourneyAdmin(admin.ModelAdmin):
    list_display = ('datetime', 'vehicle', 'service', 'route_name', 'code', 'destination')
    list_select_related = ('vehicle', 'service')
    raw_id_fields = ('vehicle', 'service')
    list_filter = (
        ('service', admin.BooleanFieldListFilter),
        ('source', admin.RelatedOnlyFieldListFilter),
        'vehicle__operator',
    )
    ordering = ('-id',)


class JourneyCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'service', 'destination']
    list_select_related = ['service']
    raw_id_fields = ['service']


class LiveryAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ['name', 'preview']


admin.site.register(VehicleType, VehicleTypeAdmin)
admin.site.register(VehicleFeature)
admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(VehicleEdit, VehicleEditAdmin)
admin.site.register(VehicleJourney, VehicleJourneyAdmin)
admin.site.register(JourneyCode, JourneyCodeAdmin)
admin.site.register(Livery, LiveryAdmin)
