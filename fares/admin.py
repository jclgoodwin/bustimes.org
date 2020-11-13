from django.contrib import admin
from .models import PriceGroup, FareZone, Tariff, UserProfile, DistanceMatrixElement, FareTable


class FareZoneAdmin(admin.ModelAdmin):
    autocomplete_fields = ["stops"]


admin.site.register(PriceGroup)
admin.site.register(Tariff)
admin.site.register(UserProfile)
admin.site.register(FareTable)
admin.site.register(DistanceMatrixElement)
admin.site.register(FareZone, FareZoneAdmin)
