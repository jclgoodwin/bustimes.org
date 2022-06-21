from django.contrib import admin
from sql_util.utils import SubqueryCount
from .models import Situation, Consequence, Link, ValidityPeriod


class ConsequenceInline(admin.StackedInline):
    model = Consequence
    autocomplete_fields = ["stops", "services", "operators"]
    readonly_fields = ["data"]
    show_change_link = True


class ValidityPeriodInline(admin.TabularInline):
    model = ValidityPeriod


class LinkInline(admin.TabularInline):
    model = Link


class SituationAdmin(admin.ModelAdmin):
    inlines = [ValidityPeriodInline, LinkInline, ConsequenceInline]
    list_display = ["__str__", "reason", "source", "current", "stops"]
    list_filter = ["reason", "source", "current"]
    readonly_fields = ["data"]

    def stops(self, obj):
        return obj.stops

    stops.admin_order_field = "stops"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(stops=SubqueryCount("consequence__stops"))
        return queryset


admin.site.register(Situation, SituationAdmin)
