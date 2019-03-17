from django import forms
from django.contrib import admin
from django.contrib.gis.forms import OSMWidget
from django.db.models import Count, Q
from django.contrib.gis.db.models import PointField
from .models import (
    Region, AdminArea, District, Locality, StopArea, StopPoint, Operator, Service, Note, Journey, StopUsageUsage,
    ServiceCode, OperatorCode, DataSource, Place, Registration, Variation, SIRISource
)


class ModelAdmin(admin.ModelAdmin):
    using = 'default'

    def get_queryset(self, request):
        # force admin interface to use the master database
        return super().get_queryset(request).using(self.using)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        return super().formfield_for_foreignkey(db_field, request, using=self.using, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        return super().formfield_for_manytomany(db_field, request, using=self.using, **kwargs)


class RelatedOnlyFieldListFilter(admin.RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        pk_qs = model_admin.get_queryset(request).using('read-only').distinct().values_list('%s__pk' % self.field_path,
                                                                                            flat=True)
        return field.get_choices(include_blank=False, limit_choices_to={'pk__in': pk_qs})


class AdminAreaAdmin(ModelAdmin):
    list_display = ('name', 'id', 'atco_code', 'region_id')
    list_filter = ('region_id',)
    search_fields = ('atco_code',)


class StopPointAdmin(ModelAdmin):
    list_display = ('atco_code', 'naptan_code', 'locality', 'admin_area', '__str__')
    list_select_related = ('locality', 'admin_area')
    list_filter = ('stop_type', 'service__region', 'admin_area')
    raw_id_fields = ('places',)
    search_fields = ('atco_code', 'common_name', 'locality__name')
    ordering = ('atco_code',)
    formfield_overrides = {
        PointField: {'widget': OSMWidget}
    }


class OperatorAdmin(ModelAdmin):
    list_display = ('name', 'operator_codes', 'id', 'vehicle_mode', 'parent', 'region', 'service_count', 'twitter')
    list_filter = ('region', 'vehicle_mode', 'parent')
    search_fields = ('id', 'name')

    def get_queryset(self, _):
        service_count = Count('service', filter=Q(service__current=True))
        return Operator.objects.annotate(service_count=service_count).prefetch_related('operatorcode_set')

    @staticmethod
    def service_count(obj):
        return obj.service_count

    @staticmethod
    def operator_codes(obj):
        return ', '.join(str(code) for code in obj.operatorcode_set.all())

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'address' or db_field.name == 'twitter':
            formfield.widget = forms.Textarea(attrs=formfield.widget.attrs)
        return formfield

    service_count.admin_order_field = 'service_count'


class ServiceAdmin(ModelAdmin):
    list_display = ('service_code', '__str__', 'mode', 'net', 'region', 'current', 'show_timetable', 'timetable_wrong')
    list_filter = ('current', 'show_timetable', 'timetable_wrong', 'mode', 'net', 'region',
                   ('operator', RelatedOnlyFieldListFilter))
    search_fields = ('service_code', 'line_name', 'description')
    raw_id_fields = ('operator', 'stops')
    ordering = ('service_code',)


class LocalityAdmin(ModelAdmin):
    list_display = ('id', 'name', 'slug')
    search_fields = ('id', 'name')
    raw_id_fields = ('adjacent',)
    list_filter = ('admin_area', 'admin_area__region')


class NoteAdmin(ModelAdmin):
    raw_id_fields = ('operators', 'services')

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'text':
            formfield.widget = forms.Textarea(attrs=formfield.widget.attrs)
        return formfield


class JourneyAdmin(ModelAdmin):
    list_display = ('id', 'service', 'datetime')
    list_filter = ('service__region',)
    raw_id_fields = ('service', 'destination')
    ordering = ('id',)


class StopUsageUsageAdmin(ModelAdmin):
    show_full_result_count = False
    list_display = ('id', 'datetime')
    raw_id_fields = ('journey', 'stop')
    ordering = ('id',)


class OperatorCodeAdmin(ModelAdmin):
    list_display = ('id', 'operator', 'source', 'code')
    list_filter = ('source',)
    search_fields = ('code',)
    raw_id_fields = ('operator',)


class ServiceCodeAdmin(ModelAdmin):
    list_display = ('id', 'service', 'scheme', 'code')
    list_filter = (
        'scheme',
        'service__current',
        ('service__operator', RelatedOnlyFieldListFilter),
        'service__stops__admin_area'
    )
    search_fields = ('code', 'service__line_name', 'service__description')
    raw_id_fields = ('service',)


class PlaceAdmin(ModelAdmin):
    list_filter = ('source',)
    search_fields = ('name',)


class VariationAdmin(ModelAdmin):
    list_filter = ('registration_status',)


class DataSourceAdmin(ModelAdmin):
    list_display = ('name', 'url', 'datetime')


class SIRISourceAdmin(ModelAdmin):
    list_display = ('name', 'url', 'requestor_ref', 'areas')

    def get_queryset(self, _):
        return self.model.objects.prefetch_related('admin_areas')

    @staticmethod
    def areas(obj):
        return ', '.join('{} ({})'.format(area, area.atco_code) for area in obj.admin_areas.all())


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
admin.site.register(OperatorCode, OperatorCodeAdmin)
admin.site.register(ServiceCode, ServiceCodeAdmin)
admin.site.register(DataSource, DataSourceAdmin)
admin.site.register(Place, PlaceAdmin)
admin.site.register(Registration)
admin.site.register(Variation, VariationAdmin)
admin.site.register(SIRISource, SIRISourceAdmin)
