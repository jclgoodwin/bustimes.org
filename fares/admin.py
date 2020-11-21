from django.contrib import admin
from .models import DataSet, Tariff, PriceGroup, FareZone, UserProfile, DistanceMatrixElement, FareTable


class DataSetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "url"]


class TariffAdmin(admin.ModelAdmin):
    autocomplete_fields = ["operators", "services"]


class FareZoneAdmin(admin.ModelAdmin):
    autocomplete_fields = ["stops"]


admin.site.register(DataSet, DataSetAdmin)
admin.site.register(Tariff, TariffAdmin)
admin.site.register(PriceGroup)
admin.site.register(UserProfile)
admin.site.register(FareTable)
admin.site.register(DistanceMatrixElement)
admin.site.register(FareZone, FareZoneAdmin)
