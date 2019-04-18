from django.contrib import admin
from .models import VehicleType, Vehicle, VehicleJourney, Livery, JourneyCode


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


class VehicleAdmin(admin.ModelAdmin):
    list_display = ('code', 'fleet_number', 'reg', 'operator', 'vehicle_type', 'livery', 'colours', 'notes')
    list_filter = (
        ('operator', admin.RelatedOnlyFieldListFilter),
        ('source', admin.RelatedOnlyFieldListFilter),
        'vehicle_type',
    )
    list_select_related = ['operator', 'vehicle_type']
    list_editable = ('fleet_number', 'reg', 'operator', 'vehicle_type', 'livery', 'colours', 'notes')
    search_fields = ('code', 'fleet_number', 'reg')
    raw_id_fields = ('operator',)
    autocomplete_fields = ('vehicle_type',)
    ordering = ('-id',)
    actions = (copy_livery, copy_type)


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
    list_display = ['name', 'preview']


admin.site.register(VehicleType, VehicleTypeAdmin)
admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(VehicleJourney, VehicleJourneyAdmin)
admin.site.register(JourneyCode, JourneyCodeAdmin)
admin.site.register(Livery, LiveryAdmin)
