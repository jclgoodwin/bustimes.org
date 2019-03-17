from django.contrib import admin
from busstops.admin import ModelAdmin, RelatedOnlyFieldListFilter
from .models import VehicleType, Vehicle, VehicleJourney


class VehicleTypeAdmin(ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'double_decker', 'coach')
    list_editable = list_display[1:]


class VehicleAdmin(ModelAdmin):
    list_display = ('code', 'fleet_number', 'reg', 'operator', 'vehicle_type', 'colours', 'notes')
    list_filter = (
        ('operator', RelatedOnlyFieldListFilter),
        ('source', RelatedOnlyFieldListFilter),
        'vehicle_type',
    )
    list_select_related = ['operator', 'vehicle_type']
    list_editable = ('fleet_number', 'reg', 'operator', 'vehicle_type', 'colours', 'notes')
    search_fields = ('code',)
    raw_id_fields = ('operator',)
    autocomplete_fields = ('vehicle_type',)
    ordering = ('-id',)


class VehicleJourneyAdmin(ModelAdmin):
    list_display = ('datetime', 'vehicle', 'service', 'code', 'destination')
    list_select_related = ('vehicle', 'service')
    raw_id_fields = ('service',)
    list_filter = (
        ('source', RelatedOnlyFieldListFilter),
    )


admin.site.register(VehicleType, VehicleTypeAdmin)
admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(VehicleJourney, VehicleJourneyAdmin)
