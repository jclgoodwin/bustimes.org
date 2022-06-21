from django import forms
from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Q, F, Exists, OuterRef, CharField
from django.db.models.functions import Cast
from django.urls import reverse
from django.utils.html import format_html

from sql_util.utils import SubqueryCount

from bustimes.models import Route
from vehicles.models import VehicleJourney
from . import models


@admin.register(models.AdminArea)
class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "id", "atco_code", "region_id")
    list_filter = ("region_id",)
    search_fields = ("atco_code",)


class StopCodeInline(admin.TabularInline):
    model = models.StopCode
    raw_id_fields = ["source"]


@admin.register(models.StopPoint)
class StopPointAdmin(GISModelAdmin):
    list_display = [
        "atco_code",
        "naptan_code",
        "locality",
        "admin_area",
        "__str__",
        "modified_at",
        "created_at",
    ]
    list_select_related = ["locality", "admin_area"]
    list_filter = [
        "modified_at",
        "created_at",
        "stop_type",
        "service__region",
        "admin_area",
    ]
    raw_id_fields = ["stop_area", "locality", "places", "admin_area"]
    search_fields = ["atco_code"]
    ordering = ["atco_code"]
    inlines = [StopCodeInline]
    show_full_result_count = False

    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return super().get_search_results(request, queryset, search_term)

        query = SearchQuery(search_term, search_type="websearch", config="english")
        rank = SearchRank(F("locality__search_vector"), query)
        query = Q(locality__search_vector=query)
        if " " not in search_term:
            query |= Q(atco_code=search_term)
        queryset = queryset.annotate(rank=rank).filter(query).order_by("-rank")
        return queryset, False


@admin.register(models.StopCode)
class StopCodeAdmin(admin.ModelAdmin):
    list_display = ["stop", "code", "source"]
    raw_id_fields = ["stop", "source"]


@admin.register(models.StopArea)
class StopAreaAdmin(GISModelAdmin):
    raw_id_fields = ["admin_area", "parent"]


class OperatorCodeInline(admin.TabularInline):
    model = models.OperatorCode


class OperatorAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            "address": forms.Textarea,
            "twitter": forms.Textarea,
        }


@admin.register(models.Operator)
class OperatorAdmin(admin.ModelAdmin):
    form = OperatorAdminForm
    list_display = [
        "name",
        "slug",
        "operator_codes",
        "id",
        "vehicle_mode",
        "parent",
        "region_id",
        "services",
        "vehicles",
        "twitter",
    ]
    list_filter = ("region", "vehicle_mode", "payment_methods", "parent")
    search_fields = ("id", "name")
    raw_id_fields = ("region", "regions", "siblings", "colour")
    inlines = [OperatorCodeInline]
    readonly_fields = ["search_vector"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("licences",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(
                services=SubqueryCount("service", filter=Q(service__current=True)),
                vehicles=SubqueryCount("vehicle"),
            ).prefetch_related("operatorcode_set")
        return queryset

    @admin.display(ordering="services")
    def services(self, obj):
        url = reverse("admin:busstops_service_changelist")
        return format_html(
            '<a href="{}?operator__id__exact={}">{}</a>', url, obj.id, obj.services
        )

    @admin.display(ordering="vehicles")
    def vehicles(self, obj):
        url = reverse("admin:vehicles_vehicle_changelist")
        return format_html(
            '<a href="{}?operator__id__exact={}">{}</a>', url, obj.id, obj.vehicles
        )

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )

        if request.path.endswith("/autocomplete/"):
            queryset = queryset.filter(
                Exists(
                    models.Service.objects.filter(operator=OuterRef("pk"), current=True)
                )
            )

        return queryset, use_distinct

    @staticmethod
    def payment(obj):
        return ", ".join(str(code) for code in obj.payment_methods.all())

    @staticmethod
    def operator_codes(obj):
        return ", ".join(str(code) for code in obj.operatorcode_set.all())


class ServiceCodeInline(admin.TabularInline):
    model = models.ServiceCode


class RouteInline(admin.TabularInline):
    model = Route
    show_change_link = True
    fields = ["source", "code", "service_code"]
    raw_id_fields = ["source"]


class FromServiceLinkInline(admin.TabularInline):
    model = models.ServiceLink
    fk_name = "from_service"
    autocomplete_fields = ["to_service"]


class ToServiceLinkInline(FromServiceLinkInline):
    fk_name = "to_service"
    autocomplete_fields = ["from_service"]


@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "__str__",
        "service_code",
        "mode",
        "region_id",
        "routes",
        "current",
        "timetable_wrong",
        "colour",
        "line_brand",
    )
    list_filter = (
        "current",
        "timetable_wrong",
        "mode",
        "region",
        ("source", admin.RelatedOnlyFieldListFilter),
        ("operator", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("service_code", "line_name", "line_brand", "description")
    raw_id_fields = ("operator", "stops", "colour", "source")
    inlines = [
        ServiceCodeInline,
        RouteInline,
        FromServiceLinkInline,
        ToServiceLinkInline,
    ]
    readonly_fields = ["search_vector"]
    list_editable = ["colour", "line_brand"]
    list_select_related = ["colour"]

    def routes(self, obj):
        return obj.routes

    routes.admin_order_field = "routes"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            queryset = queryset.annotate(routes=SubqueryCount("route"))
        return queryset

    def get_search_results(self, request, queryset, search_term):
        if search_term and request.path.endswith("/autocomplete/"):
            queryset = queryset.filter(current=True)

            query = SearchQuery(search_term, search_type="websearch", config="english")
            rank = SearchRank(F("search_vector"), query)
            queryset = (
                queryset.annotate(rank=rank)
                .filter(Q(search_vector=query) | Q(service_code=search_term))
                .order_by("-rank")
            )
            return queryset, False

        return super().get_search_results(request, queryset, search_term)


@admin.register(models.ServiceLink)
class ServiceLinkAdmin(admin.ModelAdmin):
    save_as = True
    list_display = (
        "from_service",
        "from_service__current",
        "to_service",
        "to_service__current",
        "how",
    )
    list_filter = (
        "from_service__current",
        "to_service__current",
        "from_service__source",
        "to_service__source",
    )
    autocomplete_fields = ("from_service", "to_service")

    @staticmethod
    def from_service__current(obj):
        return obj.from_service.current

    @staticmethod
    def to_service__current(obj):
        return obj.to_service.current


@admin.register(models.Locality)
class LocalityAdmin(GISModelAdmin):
    list_display = ("id", "name", "slug", "modified_at", "created_at")
    search_fields = ("id", "name")
    raw_id_fields = ("adjacent", "parent")
    list_filter = ("modified_at", "created_at", "admin_area__region", "admin_area")


@admin.register(models.OperatorCode)
class OperatorCodeAdmin(admin.ModelAdmin):
    save_as = True
    list_display = ("id", "operator", "source", "code")
    list_filter = [("source", admin.RelatedOnlyFieldListFilter)]
    search_fields = ("code",)
    raw_id_fields = ("operator",)


@admin.register(models.ServiceCode)
class ServiceCodeAdmin(admin.ModelAdmin):
    list_display = ["id", "service", "scheme", "code"]
    list_filter = [
        "scheme",
        "service__current",
        ("service__operator", admin.RelatedOnlyFieldListFilter),
        "service__stops__admin_area",
    ]
    search_fields = ["code", "service__line_name", "service__description"]
    autocomplete_fields = ["service"]


@admin.register(models.ServiceColour)
class ServiceColourAdmin(admin.ModelAdmin):
    list_display = ["preview", "foreground", "background", "services"]
    search_fields = ["name"]
    list_filter = [("service__operator", admin.EmptyFieldListFilter)]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            queryset = queryset.annotate(
                services=SubqueryCount("service", filter=Q(current=True))
            )
        return queryset

    def services(self, obj):
        return obj.services

    services.admin_order_field = "services"


@admin.register(models.Place)
class PlaceAdmin(admin.ModelAdmin):
    list_filter = ("source",)
    search_fields = ("name",)
    raw_id_fields = ("parent",)


@admin.register(models.DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    search_fields = ("name", "url")
    list_display = (
        "name",
        "url",
        "sha1",
        "datetime",
        "settings",
        "routes",
        "services",
        "journeys",
    )
    list_filter = (
        ("route", admin.EmptyFieldListFilter),
        ("service", admin.EmptyFieldListFilter),
        ("vehiclejourney", admin.EmptyFieldListFilter),
    )
    actions = ["delete_routes", "remove_datetimes"]
    show_full_result_count = False
    ordering = ("name",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(
                routes=SubqueryCount("route"),
                services=SubqueryCount("service", filter=Q(current=True)),
                journeys=Exists(VehicleJourney.objects.filter(source=OuterRef("id"))),
            ).prefetch_related("operatorcode_set")
        return queryset

    def routes(self, obj):
        url = reverse("admin:bustimes_route_changelist")
        return format_html(
            '<a href="{}?source__id__exact={}">{}</a>', url, obj.id, obj.routes
        )

    routes.admin_order_field = "routes"

    def services(self, obj):
        url = reverse("admin:busstops_service_changelist")
        return format_html(
            '<a href="{}?source__id__exact={}">{}</a>', url, obj.id, obj.services
        )

    services.admin_order_field = "services"

    def journeys(self, obj):
        url = reverse("admin:vehicles_vehiclejourney_changelist")
        return format_html(
            '<a href="{}?source__id__exact={}">{}</a>', url, obj.id, obj.journeys
        )

    journeys.admin_order_field = "journeys"

    def delete_routes(self, request, queryset):
        result = Route.objects.filter(source__in=queryset).delete()
        self.message_user(request, result)

    def remove_datetimes(self, request, queryset):
        result = queryset.order_by().update(datetime=None)
        self.message_user(request, result)


@admin.register(models.SIRISource)
class SIRISourceAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "requestor_ref", "areas", "get_poorly")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(
                areas=StringAgg(
                    Cast("admin_areas__atco_code", output_field=CharField()), ", "
                )
            )
        return queryset

    @staticmethod
    def areas(obj):
        return obj.areas


class PaymentMethodOperatorInline(admin.TabularInline):
    model = models.PaymentMethod.operator_set.through
    autocomplete_fields = ["operator"]


@admin.register(models.PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "operators")
    inlines = [PaymentMethodOperatorInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(
                operators=StringAgg("operator", ", ", distinct=True)
            )
        return queryset

    @staticmethod
    def operators(obj):
        return obj.operators


admin.site.register(models.Region)
admin.site.register(models.District)
