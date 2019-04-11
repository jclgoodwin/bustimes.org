from django.contrib import admin
from .models import VehicleType, Vehicle, VehicleJourney, Livery, JourneyCode


class VehicleTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'double_decker', 'coach')
    list_editable = list_display[1:]


class VehicleAdmin(admin.ModelAdmin):
    list_display = ('code', 'fleet_number', 'reg', 'operator', 'vehicle_type', 'colours', 'notes')
    list_filter = (
        ('operator', admin.RelatedOnlyFieldListFilter),
        ('source', admin.RelatedOnlyFieldListFilter),
        'vehicle_type',
    )
    list_select_related = ['operator', 'vehicle_type']
    list_editable = ('fleet_number', 'reg', 'operator', 'vehicle_type', 'colours', 'notes')
    search_fields = ('code', 'fleet_number', 'reg')
    raw_id_fields = ('operator',)
    autocomplete_fields = ('vehicle_type',)
    ordering = ('-id',)


class VehicleJourneyAdmin(admin.ModelAdmin):
    list_display = ('datetime', 'vehicle', 'service', 'code', 'destination')
    list_select_related = ('vehicle', 'service')
    raw_id_fields = ('service',)
    list_filter = (
        ('source', admin.RelatedOnlyFieldListFilter),
    )
    ordering = ('-id',)


class JourneyCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'service', 'destination']
    list_select_related = ['service']
    raw_id_fields = ['service']


admin.site.register(VehicleType, VehicleTypeAdmin)
admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(VehicleJourney, VehicleJourneyAdmin)
admin.site.register(JourneyCode, JourneyCodeAdmin)
admin.site.register(Livery)
