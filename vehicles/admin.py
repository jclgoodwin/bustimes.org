from django.contrib import admin
from django.contrib.gis.forms import OSMWidget
from django.contrib.gis.db.models import PointField
from .models import VehicleType, Vehicle, VehicleLocation


class VehicleTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'double_decker')


class VehicleAdmin(admin.ModelAdmin):
    list_display = ('code', 'fleet_number', 'reg', 'operator', 'vehicle_type', 'colours')
    list_filter = (
        ('operator', admin.RelatedOnlyFieldListFilter),
        ('source', admin.RelatedOnlyFieldListFilter),
        ('vehicle_type', admin.RelatedOnlyFieldListFilter),
    )
    list_select_related = ('operator', 'vehicle_type')
    list_editable = ('fleet_number', 'reg', 'operator', 'vehicle_type', 'colours')
    search_fields = ('code',)
    raw_id_fields = ('operator',)
    autocomplete_fields = ('vehicle_type',)
    ordering = ('-id',)


class VehicleLocationAdmin(admin.ModelAdmin):
    show_full_result_count = False
#     list_display = ('vehicle', 'service', 'datetime')
#     list_filter = (
#         'current',
#         ('service__operator', admin.RelatedOnlyFieldListFilter),
#         ('service', admin.RelatedOnlyFieldListFilter),
#         ('source', admin.RelatedOnlyFieldListFilter),
#     )
    raw_id_fields = ('journey',)
    formfield_overrides = {
        PointField: {'widget': OSMWidget}
    }


admin.site.register(VehicleType, VehicleTypeAdmin)
admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(VehicleLocation)
