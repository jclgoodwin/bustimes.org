from django import forms
from django.contrib import admin
from django.db.models import Count
from busstops.models import (
    Region, AdminArea, District, Locality, StopArea, StopPoint, Operator, Service, Note, Journey, StopUsageUsage
)


class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'atco_code', 'region_id')
    list_filter = ('region_id',)


class StopPointAdmin(admin.ModelAdmin):
    list_display = ('atco_code', 'naptan_code', 'locality', 'admin_area', '__str__')
    list_select_related = ('locality', 'admin_area')
    list_filter = ('admin_area',)
    search_fields = ('common_name',)
    ordering = ('atco_code',)


class OperatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'vehicle_mode', 'parent', 'region', 'service_count')
    list_filter = ('region', 'vehicle_mode', 'parent')
    search_fields = ('id', 'name')
    ordering = ('id',)

    def get_queryset(self, _):
        return Operator.objects.annotate(service_count=Count('service'))

    def service_count(self, obj):
        return obj.service_count

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super(OperatorAdmin, self).formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'address':
            formfield.widget = forms.Textarea(attrs=formfield.widget.attrs)
        return formfield

    service_count.admin_order_field = 'service_count'


class ServiceAdmin(admin.ModelAdmin):
    list_display = ('service_code', '__str__', 'mode', 'net', 'region', 'current', 'show_timetable')
    list_filter = ('show_timetable', 'current', 'mode', 'net', 'region', ('operator', admin.RelatedOnlyFieldListFilter))
    search_fields = ('service_code', 'line_name', 'description')
    raw_id_fields = ('operator', 'stops')
    ordering = ('service_code',)


class LocalityAdmin(admin.ModelAdmin):
    search_fields = ('id', 'name')
    raw_id_fields = ('adjacent',)
    list_filter = ('admin_area', 'admin_area__region')


class NoteAdmin(admin.ModelAdmin):
    raw_id_fields = ('operators', 'services')


class JourneyAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'datetime')
    list_filter = ('service__region',)
    raw_id_fields = ('service', 'destination')
    ordering = ('id',)


class StopUsageUsageAdmin(admin.ModelAdmin):
    list_display = ('id', 'datetime')
    raw_id_fields = ('journey', 'stop')
    ordering = ('id',)


admin.site.register(Region)
admin.site.register(AdminArea, AdminAreaAdmin)
admin.site.register(District)
admin.site.register(Locality, LocalityAdmin)
admin.site.register(StopArea)
admin.site.register(StopPoint, StopPointAdmin)
admin.site.register(Operator, OperatorAdmin)
admin.site.register(Service, ServiceAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Journey, JourneyAdmin)
admin.site.register(StopUsageUsage, StopUsageUsageAdmin)
