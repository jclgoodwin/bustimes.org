from django.contrib import admin
from .models import Licence, Registration, Variation


class LicenceAdmin(admin.ModelAdmin):
    search_fields = ['licence_number', 'name', 'trading_name']
    list_display = ['licence_number', 'name', 'trading_name']
    list_filter = ['traffic_area']


class RegistrationAdmin(admin.ModelAdmin):
    list_display = ['registration_number']


class VariationAdmin(admin.ModelAdmin):
    list_display = ['variation_number']


admin.site.register(Licence, LicenceAdmin)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(Variation, VariationAdmin)
