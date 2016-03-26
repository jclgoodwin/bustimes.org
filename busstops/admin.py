from django.contrib import admin
from django.db.models import Count
from busstops.models import Region, AdminArea, District, Locality, StopArea, StopPoint, Operator, Service

class StopPointAdmin(admin.ModelAdmin):
    list_display = ('atco_code', 'naptan_code', 'locality', 'admin_area', '__unicode__')
    list_filter = ('stop_type', 'bus_stop_type', 'timing_status')
    search_fields = ('common_name',)
    ordering = ('atco_code',)


class OperatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'vehicle_mode', 'parent', 'region', 'service_count')
    list_filter = ('region', 'vehicle_mode', 'parent')
    search_fields = ('id', 'name')
    ordering = ('id',)

    def get_queryset(self, request):
        return Operator.objects.annotate(service_count=Count('service'))

    def service_count(self, obj):
        return obj.service_count

    service_count.admin_order_field = 'service_count'


class ServiceAdmin(admin.ModelAdmin):
    list_display = ('service_code', '__unicode__', 'mode', 'net', 'region', 'current', 'show_timetable')
    list_filter = ('show_timetable', 'current', ('operator', admin.RelatedOnlyFieldListFilter), 'mode', 'net', 'region')
    search_fields = ('service_code', 'line_name', 'description')
    raw_id_fields = ('operator',)
    ordering = ('service_code',)


admin.site.register(Region)
admin.site.register(AdminArea)
admin.site.register(District)
admin.site.register(Locality)
admin.site.register(StopArea)
admin.site.register(StopPoint, StopPointAdmin)
admin.site.register(Operator, OperatorAdmin)
admin.site.register(Service, ServiceAdmin)
