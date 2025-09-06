from django.contrib import admin
from sql_util.utils import SubqueryCount

from .models import Consequence, Link, Situation, ValidityPeriod, AffectedJourney


class ConsequenceInline(admin.StackedInline):
    model = Consequence
    autocomplete_fields = ["stops", "services", "operators"]
    readonly_fields = ["data"]
    show_change_link = True


class ValidityPeriodInline(admin.TabularInline):
    model = ValidityPeriod


class LinkInline(admin.TabularInline):
    model = Link


class AffectedJourneyInline(admin.TabularInline):
    model = AffectedJourney
    raw_id_fields = ["trip"]


@admin.register(AffectedJourney)
class AffectedJourneyAdmin(admin.ModelAdmin):
    raw_id_fields = ["trip", "situation"]
    list_filter = ["condition", ("trip__operator", admin.RelatedOnlyFieldListFilter)]


@admin.register(Situation)
class SituationAdmin(admin.ModelAdmin):
    inlines = [
        ValidityPeriodInline,
        LinkInline,
        ConsequenceInline,
        AffectedJourneyInline,
    ]
    list_display = [
        "__str__",
        "reason",
        "participant_ref",
        "source",
        "current",
        "stops",
        "created_at",
        "modified_at",
    ]
    list_filter = [
        "current",
        "source",
        "participant_ref",
        "reason",
        "created_at",
        "modified_at",
    ]
    readonly_fields = [
        "created_at",
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
