from django.contrib import admin
from .models import Licence, Registration, Variation


class LicenceAdmin(admin.ModelAdmin):
    search_fields = ["licence_number", "name", "trading_name"]
    list_display = ["licence_number", "name", "trading_name"]
    list_filter = ["traffic_area", "description", "licence_status"]


class RegistrationAdmin(admin.ModelAdmin):
    search_fields = ["registration_number"]
    list_display = ["registration_number"]
    list_filter = ["registration_status"]
    raw_id_fields = ["licence", "latest_variation"]


class VariationAdmin(admin.ModelAdmin):
    list_display = [
        "variation_number",
        "service_type_other_details",
        "registration_status",
        "effective_date",
        "date_received",
    ]
    list_filter = ["registration_status"]
    raw_id_fields = ["registration"]


admin.site.register(Licence, LicenceAdmin)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(Variation, VariationAdmin)
