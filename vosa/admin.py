from django.contrib import admin
from django.contrib.postgres.aggregates import StringAgg

from .models import Licence, Registration, Variation


class LicenceAdmin(admin.ModelAdmin):
    search_fields = ["licence_number", "name", "trading_name"]
    list_display = ["licence_number", "name", "trading_name", "operators"]
    list_filter = ["traffic_area", "description", "licence_status"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            queryset = queryset.annotate(operators=StringAgg("operator", " "))
        return queryset

    def operators(self, obj):
        return obj.operators

    operators.admin_order_field = "operators"


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
