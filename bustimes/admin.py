from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.gis.db.models import CharField
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Exists, OuterRef
from django.db.models.functions import Cast
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.html import format_html

from .models import (
    BankHoliday,
    BankHolidayDate,
    Calendar,
    CalendarBankHoliday,
    CalendarDate,
    Garage,
    Note,
    Route,
    StopTime,
    TimetableDataSource,
    Trip,
)


class TripInline(admin.TabularInline):
    model = Trip
    show_change_link = True
    raw_id_fields = [
        "destination",
        "notes",
        "calendar",
        "garage",
        "vehicle_type",
        "operator",
        "next_trip",
    ]
    fields = ["start", "end", "destination", "inbound", "calendar"]


class StopTimeInline(admin.TabularInline):
    model = StopTime
    autocomplete_fields = ["stop"]


@admin.register(TimetableDataSource)
class TimetableDataSourceAdmin(admin.ModelAdmin):
    autocomplete_fields = ["operators"]
    list_display = ["id", "name", "url", "nocs", "active", "complete", "sources"]
    list_filter = ["active", "complete"]
    search_fields = ["url", "name", "search"]
    actions = ["activate", "deactivate"]

    def nocs(self, obj):
        return obj.nocs

    def sources(self, obj):
        url = reverse("admin:busstops_datasource_changelist")
        return format_html('<a href="{}?source__id__exact={}">Sources</a>', url, obj.id)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(nocs=StringAgg("operators", ", ", distinct=True))
        return queryset

    def activate(self, request, queryset):
        count = queryset.order_by().update(active=True)
        self.message_user(request, f"Activated {count}")

    def deactivate(self, request, queryset):
        count = queryset.order_by().update(active=False)
        self.message_user(request, f"Deactivated {count}")


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["__str__", "code", "start_date", "end_date"]
    list_filter = [("source", admin.RelatedOnlyFieldListFilter)]
    raw_id_fields = ["source", "service", "registration"]
    search_fields = ["code"]
    # inlines = [TripInline]


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_filter = [("calendar", admin.EmptyFieldListFilter)]
    raw_id_fields = ["route"] + TripInline.raw_id_fields
    # inlines = [StopTimeInline]


class CalendarDateInline(admin.TabularInline):
    model = CalendarDate


class CalendarBankHolidayInline(admin.TabularInline):
    model = CalendarBankHoliday
    select_related = ["bank_holiday"]


@admin.register(CalendarDate)
class CalendarDateAdmin(admin.ModelAdmin):
    list_display = ["__str__", "start_date", "end_date"]
    list_filter = ["start_date", "end_date", ("summary", admin.EmptyFieldListFilter)]
    raw_id_fields = ["calendar"]


@admin.register(Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__", "summary"]
    inlines = [CalendarDateInline, CalendarBankHolidayInline]
    list_filter = [("trip", admin.EmptyFieldListFilter)]
    readonly_fields = ["routes"]
    save_as = True

    def routes(self, obj):
        routes = Route.objects.filter(
            Exists(Trip.objects.filter(calendar=obj, route=OuterRef("pk")))
        )
        routes = (
            (reverse("admin:bustimes_route_change", args=(route.id,)), route)
            for route in routes
        )
        return mark_safe(
            "<br>".join(f'<a href="{url}">{route}</a>' for url, route in routes)
        )


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["code", "text"]
    search_fields = ["code", "text"]


@admin.register(Garage)
class GarageAdmin(GISModelAdmin):
    search_fields = ["code", "name"]
    list_display = ["code", "name", "operators"]
    list_filter = [
        ("vehicle", admin.EmptyFieldListFilter),
        ("trip", admin.EmptyFieldListFilter),
        ("vehicle__operator", admin.RelatedOnlyFieldListFilter),
    ]
    raw_id_fields = ["operator"]

    def operators(self, obj):
        return obj.operators

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(
                operators=StringAgg("vehicle__operator", ", ", distinct=True)
            )
        return queryset


class BankHolidayDateInline(admin.StackedInline):
    model = BankHolidayDate


@admin.register(BankHoliday)
class BankHolidayAdmin(admin.ModelAdmin):
    inlines = [BankHolidayDateInline]
    list_display = ["name", "dates"]

    def dates(self, obj):
        return obj.dates

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(
                dates=StringAgg(
                    Cast("bankholidaydate__date", output_field=CharField()), ", "
                )
            )
        return queryset
