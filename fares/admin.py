from django.contrib import admin
from django.contrib.postgres.aggregates import StringAgg
from .models import DataSet, Tariff, Price, FareZone, UserProfile, DistanceMatrixElement, FareTable


class DataSetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "description", "noc", "datetime"]
    list_filter = ["published"]
    autocomplete_fields = ["operators"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if 'changelist' in request.resolver_match.view_name:
            return queryset.annotate(noc=StringAgg('operators', ', ', distinct=True))
        return queryset

    def noc(self, obj):
        return obj.noc


class TariffAdmin(admin.ModelAdmin):
    autocomplete_fields = ["operators", "services"]
    list_filter = [
       ('operators', admin.RelatedOnlyFieldListFilter)
    ]
    raw_id_fields = ["source", "user_profile", "access_zones"]


class PriceAdmin(admin.ModelAdmin):
    raw_id_fields = ["time_interval", "user_profile", "sales_offer_package", "tariff"]
    list_display = ["amount"]


class FareTableAdmin(admin.ModelAdmin):
    list_display = ["__str__", "description"]
    list_filter = ["tariff__source"]
    raw_id_fields = ["user_profile", "sales_offer_package", "tariff"]


class DistanceMatrixElementAdmin(admin.ModelAdmin):
    raw_id_fields = ["price", "start_zone", "end_zone", "tariff"]


class FareZoneAdmin(admin.ModelAdmin):
    autocomplete_fields = ["stops"]


admin.site.register(DataSet, DataSetAdmin)
admin.site.register(Tariff, TariffAdmin)
admin.site.register(Price, PriceAdmin)
admin.site.register(UserProfile)
admin.site.register(FareTable, FareTableAdmin)
admin.site.register(DistanceMatrixElement, DistanceMatrixElementAdmin)
admin.site.register(FareZone, FareZoneAdmin)
