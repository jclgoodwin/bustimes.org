from django.contrib import admin
from sql_util.utils import SubqueryCount

from .models import Consequence, Link, Situation, ValidityPeriod


class ConsequenceInline(admin.StackedInline):
    model = Consequence
    autocomplete_fields = ["stops", "services", "operators"]
    readonly_fields = ["data"]
    show_change_link = True


class ValidityPeriodInline(admin.TabularInline):
    model = ValidityPeriod


class LinkInline(admin.TabularInline):
    model = Link


@admin.register(Situation)
class SituationAdmin(admin.ModelAdmin):
    inlines = [ValidityPeriodInline, LinkInline, ConsequenceInline]
    list_display = [
        "__str__",
        "reason",
        "participant_ref",
        "source",
        "current",
        "stops",
    ]
    list_filter = ["current", "source", "participant_ref", "reason"]
    readonly_fields = [
        "created",
        "situation_number",
        "reason",
        "participant_ref",
        "data",
    ]

    @admin.display(ordering="stops")
    def stops(self, obj):
        return obj.stops

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            queryset = queryset.annotate(stops=SubqueryCount("consequence__stops"))
        return queryset
