from django import forms
from django.contrib import admin
from django.db.models import Count
from busstops.models import (
    Region, AdminArea, District, Locality, StopArea, StopPoint, Operator, Service, Note, Journey, StopUsageUsage,
    Image, ServiceCode, OperatorCode, DataSource, LiveSource
)


class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'atco_code', 'region_id')
    list_filter = ('region_id',)


class StopPointAdmin(admin.ModelAdmin):
    list_display = ('atco_code', 'naptan_code', 'locality', 'admin_area', '__str__')
    list_select_related = ('locality', 'admin_area')
    list_filter = ('service__region', 'admin_area')
    search_fields = ('atco_code', 'common_name')
    ordering = ('atco_code',)


class OperatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'operator_codes', 'id', 'vehicle_mode', 'parent', 'region', 'service_count')
    list_filter = ('region', 'vehicle_mode', 'parent')
    search_fields = ('id', 'name')

    def get_queryset(self, _):
        return Operator.objects.annotate(service_count=Count('service')).prefetch_related('operatorcode_set')

    @staticmethod
    def service_count(obj):
        return obj.service_count

    @staticmethod
    def operator_codes(obj):
        return ', '.join(str(code) for code in obj.operatorcode_set.all())

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
    list_display = ('id', 'name', 'slug')
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


class OperatorCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'operator', 'source', 'code')
    list_filter = ('source',)
    raw_id_fields = ('operator',)


class ServiceCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'scheme', 'code')
    list_filter = ('scheme',)
    raw_id_fields = ('service',)


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
admin.site.register(Image)
admin.site.register(OperatorCode, OperatorCodeAdmin)
admin.site.register(ServiceCode, ServiceCodeAdmin)
admin.site.register(DataSource)
admin.site.register(LiveSource)
