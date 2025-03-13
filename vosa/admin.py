from django.forms import ModelForm, Textarea
from django.contrib import admin
from django.contrib.postgres.aggregates import StringAgg

from .models import Licence, Registration, Variation


class OperatorInline(admin.TabularInline):
    model = Licence.operator_set.through
    autocomplete_fields = ["operator"]


class LicenceAdminForm(ModelForm):
    class Meta:
        widgets = {
            "trading_name": Textarea,
        }


@admin.register(Licence)
class LicenceAdmin(admin.ModelAdmin):
    form = LicenceAdminForm
    search_fields = ["licence_number", "name", "trading_name"]
    list_display = ["licence_number", "name", "trading_name", "operators"]
    list_filter = ["traffic_area", "description", "licence_status"]
    inlines = [OperatorInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            queryset = queryset.annotate(operators=StringAgg("operator", " "))
        return queryset

    @admin.display(ordering="operators")
    def operators(self, obj):
        return obj.operators


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    search_fields = ["registration_number"]
    list_display = ["registration_number"]
    list_filter = ["registration_status"]
    raw_id_fields = ["licence", "latest_variation"]


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = [
        "variation_number",
        "service_type_other_details",
        "registration_status",
        "effective_date",
        "date_received",
    ]
    list_filter = ["effective_date", "date_received", "registration_status"]
    raw_id_fields = ["registration"]
