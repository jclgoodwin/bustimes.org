from django import forms
from django.contrib import admin
from .models import VehicleType, VehicleFeature, Vehicle, VehicleEdit, VehicleJourney, Livery, JourneyCode


def copy_livery(modeladmin, request, queryset):
    livery = Livery.objects.filter(vehicle__in=queryset).first()
    count = queryset.update(livery=livery)
    modeladmin.message_user(request, f'Copied {livery} to {count} vehicles.')


def copy_type(modeladmin, request, queryset):
    vehicle_type = VehicleType.objects.filter(vehicle__in=queryset).first()
    count = queryset.update(vehicle_type=vehicle_type)
    modeladmin.message_user(request, f'Copied {vehicle_type} to {count} vehicles.')


def apply_edits(modeladmin, request, queryset):
    for edit in queryset:
        vehicle = edit.vehicle
        vehicle.reg = edit.reg
        vehicle.fleet_number = edit.fleet_number
        vehicle.vehicle_type = VehicleType.objects.get(name=edit.vehicle_type)
        vehicle.livery_id = edit.livery_id
        vehicle.colours = edit.colours
        vehicle.notes = edit.notes
        vehicle.save()
        edit.delete()
    modeladmin.message_user(request, 'Applied edits.')


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
    actions = (copy_livery, copy_type)

    def last_seen(self, obj):
        if obj.latest_location:
            return obj.latest_location.datetime

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', VehicleAdminForm)
        return super().get_changelist_form(request, **kwargs)


class VehicleEditAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'fleet_number', 'reg', 'vehicle_type', 'livery_preview', 'colours_preview', 'notes',
                    'flickr']
    list_select_related = ['vehicle', 'livery']
    raw_id_fields = ['vehicle', 'livery']
    actions = [apply_edits]

    def livery_preview(self, obj):
        return obj.livery.preview()

    def colours_preview(self, obj):
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
