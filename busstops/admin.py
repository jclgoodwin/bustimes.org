from django import forms
from django.contrib import admin
from django.contrib.gis.forms import OSMWidget
from django.db.models import Count, Q
from django.contrib.gis.db.models import PointField
from .models import (
    Region, AdminArea, District, Locality, StopArea, StopPoint, StopCode, Operator, Service, ServiceLink,
    Note, Journey, StopUsageUsage, ServiceCode, OperatorCode, DataSource, Place, SIRISource, PaymentMethod
)


class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'atco_code', 'region_id')
    list_filter = ('region_id',)
    search_fields = ('atco_code',)


class StopCodeInline(admin.TabularInline):
    model = StopCode


class StopPointAdmin(admin.ModelAdmin):
    list_display = ('atco_code', 'naptan_code', 'locality', 'admin_area', '__str__')
    list_select_related = ('locality', 'admin_area')
    list_filter = ('stop_type', 'service__region', 'admin_area')
    raw_id_fields = ('places',)
    search_fields = ('atco_code', 'common_name', 'locality__name')
    ordering = ('atco_code',)
    formfield_overrides = {
        PointField: {'widget': OSMWidget}
    }
    inlines = [StopCodeInline]


class StopCodeAdmin(admin.ModelAdmin):
    list_display = ['stop', 'code', 'source']
    raw_id_fields = ['stop']


class OperatorCodeInline(admin.TabularInline):
    model = OperatorCode


class OperatorAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            'address': forms.Textarea,
            'twitter': forms.Textarea,
        }


class OperatorAdmin(admin.ModelAdmin):
    form = OperatorAdminForm
    list_display = ('name', 'operator_codes', 'id', 'vehicle_mode', 'parent', 'region', 'service_count', 'twitter',
                    'payment')
    list_filter = ('region', 'vehicle_mode', 'payment_methods', 'parent')
    search_fields = ('id', 'name')
    inlines = [OperatorCodeInline]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ('licences',)

    def get_queryset(self, _):
        service_count = Count('service', filter=Q(service__current=True))
        return Operator.objects.annotate(service_count=service_count).prefetch_related('operatorcode_set',
                                                                                       'payment_methods')

    @staticmethod
    def service_count(obj):
        return obj.service_count

    @staticmethod
    def payment(obj):
        return ', '.join(str(code) for code in obj.payment_methods.all())

    @staticmethod
    def operator_codes(obj):
        return ', '.join(str(code) for code in obj.operatorcode_set.all())

    service_count.admin_order_field = 'service_count'


class ServiceCodeInline(admin.TabularInline):
    model = ServiceCode


class ServiceAdmin(admin.ModelAdmin):
    list_display = ('service_code', '__str__', 'mode', 'net', 'region', 'current', 'show_timetable', 'timetable_wrong')
    list_filter = ('current', 'show_timetable', 'timetable_wrong', 'mode', 'net', 'region',
                   ('source', admin.RelatedOnlyFieldListFilter),
                   ('operator', admin.RelatedOnlyFieldListFilter))
    search_fields = ('service_code', 'line_name', 'line_brand', 'description')
    raw_id_fields = ('operator', 'stops')
    ordering = ('service_code',)
    inlines = [ServiceCodeInline]

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        if request.path.endswith('/autocomplete/'):
            queryset = queryset.filter(current=True)

        return queryset, use_distinct


class ServiceLinkAdmin(admin.ModelAdmin):
    list_display = ('from_service', 'from_service__current', 'to_service', 'to_service__current', 'how')
    autocomplete_fields = ('from_service', 'to_service')

    @staticmethod
    def from_service__current(obj):
        return obj.from_service.current

    @staticmethod
    def to_service__current(obj):
        return obj.to_service.current


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
    show_full_result_count = False
    list_display = ('id', 'datetime')
    raw_id_fields = ('journey', 'stop')
    ordering = ('id',)


class OperatorCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'operator', 'source', 'code')
    list_filter = ('source',)
    search_fields = ('code',)
    raw_id_fields = ('operator',)


class ServiceCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'scheme', 'code')
    list_filter = (
        'scheme',
        'service__current',
        ('service__operator', admin.RelatedOnlyFieldListFilter),
        'service__stops__admin_area'
    )
    search_fields = ('code', 'service__line_name', 'service__description')
    raw_id_fields = ('service',)


class PlaceAdmin(admin.ModelAdmin):
    list_filter = ('source',)
    search_fields = ('name',)


class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'datetime')


class SIRISourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'requestor_ref', 'areas', 'get_poorly')

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
admin.site.register(StopCode, StopCodeAdmin)
admin.site.register(StopPoint, StopPointAdmin)
admin.site.register(Operator, OperatorAdmin)
admin.site.register(Service, ServiceAdmin)
admin.site.register(ServiceLink, ServiceLinkAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Journey, JourneyAdmin)
admin.site.register(StopUsageUsage, StopUsageUsageAdmin)
admin.site.register(OperatorCode, OperatorCodeAdmin)
admin.site.register(ServiceCode, ServiceCodeAdmin)
admin.site.register(DataSource, DataSourceAdmin)
admin.site.register(Place, PlaceAdmin)
admin.site.register(SIRISource, SIRISourceAdmin)
admin.site.register(PaymentMethod)
