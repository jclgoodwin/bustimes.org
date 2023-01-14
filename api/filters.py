from django.db.models import Q
from django_filters.rest_framework import CharFilter, FilterSet, NumberFilter

from busstops.models import Operator, Service, StopPoint
from vehicles.models import Vehicle


class VehicleFilter(FilterSet):
    search = CharFilter(method="search_filter", label="Search")
    fleet_code = CharFilter(lookup_expr="iexact")
    reg = CharFilter(lookup_expr="iexact")
    slug = CharFilter()
    operator = CharFilter()

    def search_filter(self, queryset, name, value):
        return queryset.filter(Q(reg__iexact=value) | Q(fleet_code__iexact=value))

    class Meta:
        model = Vehicle
        fields = ["id", "vehicle_type", "livery", "withdrawn"]


class VehicleJourneyFilter(FilterSet):
    vehicle = NumberFilter()
    service = NumberFilter()
    trip = NumberFilter()
    source = NumberFilter()


class StopFilter(FilterSet):
    class Meta:
        model = StopPoint
        fields = ["atco_code", "naptan_code", "stop_type"]


class ServiceFilter(FilterSet):
    class Meta:
        model = Service
        fields = ["public_use", "operator"]


class OperatorFilter(FilterSet):
    class Meta:
        model = Operator
        fields = ["name", "slug", "vehicle_mode", "parent", "region_id"]
