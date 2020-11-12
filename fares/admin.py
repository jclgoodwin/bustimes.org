from django.contrib import admin
from .models import Price, FareZone


class FareZoneAdmin(admin.ModelAdmin):
    autocomplete_fields = ["stops"]


admin.site.register(Price)
admin.site.register(FareZone, FareZoneAdmin)
