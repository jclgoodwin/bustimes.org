from django.contrib import admin
from django.db.models import Exists, OuterRef
from django.db.models.functions import Cast
from django.contrib.gis.db.models import CharField
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.postgres.aggregates import StringAgg
from django.utils.safestring import mark_safe
from django.urls import reverse
from .models import (
    Route,
    Trip,
    Calendar,
    CalendarDate,
    CalendarBankHoliday,
    BankHoliday,
    BankHolidayDate,
    Note,
    StopTime,
    Garage,
    TimetableDataSource,
)


class TripInline(admin.TabularInline):
    model = Trip
    show_change_link = True
    raw_id_fields = [
        "block",
        "destination",
        "notes",
        "calendar",
        "garage",
        "vehicle_type",
        "operator",
    ]
    fields = ["start", "end", "destination", "inbound", "calendar"]


class StopTimeInline(admin.TabularInline):
    model = StopTime
    autocomplete_fields = ["stop"]


@admin.register(TimetableDataSource)
class TimetableDataSourceAdmin(admin.ModelAdmin):
    raw_id_fields = ["operators"]
    list_display = ["id", "name", "url", "nocs", "active"]
    list_filter = ["active"]
    search_fields = ["url"]

    def nocs(self, obj):
        return obj.nocs

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(nocs=StringAgg("operators", ", ", distinct=True))
        return queryset


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["__str__", "code", "start_date", "end_date"]
    list_filter = [("source", admin.RelatedOnlyFieldListFilter)]
    raw_id_fields = ["source", "service", "registration"]
    search_fields = ["line_name", "line_brand", "description"]
    inlines = [TripInline]


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    raw_id_fields = ["route"] + TripInline.raw_id_fields
    inlines = [StopTimeInline]
    list_filter = [("calendar", admin.EmptyFieldListFilter)]


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
