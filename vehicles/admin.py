from django import forms
from django.contrib import admin
from .models import VehicleType, VehicleFeature, Vehicle, VehicleJourney, Livery, JourneyCode


def copy_livery(modeladmin, request, queryset):
    livery = Livery.objects.filter(vehicle__in=queryset).first()
    queryset.update(livery=livery)


def copy_type(modeladmin, request, queryset):
    vehicle_type = VehicleType.objects.filter(vehicle__in=queryset).first()
    queryset.update(vehicle_type=vehicle_type)


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
    search_fields = ('code', 'fleet_number', 'reg')
    autocomplete_fields = ('vehicle_type', 'livery')
    ordering = ('-id',)
    actions = (copy_livery, copy_type)

    def last_seen(self, obj):
        if obj.latest_location:
            return obj.latest_location.datetime

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', VehicleAdminForm)
        return super().get_changelist_form(request, **kwargs)


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
admin.site.register(VehicleJourney, VehicleJourneyAdmin)
admin.site.register(JourneyCode, JourneyCodeAdmin)
admin.site.register(Livery, LiveryAdmin)
