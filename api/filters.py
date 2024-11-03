from django.db.models import Q
from django_filters.rest_framework import (
    CharFilter,
    DateTimeFilter,
    FilterSet,
    NumberFilter,
    OrderingFilter,
)

from busstops.models import Operator, Service, StopPoint
from bustimes.models import Trip
from vehicles.models import Livery, Vehicle, VehicleType


class VehicleFilter(FilterSet):
    search = CharFilter(method="search_filter", label="Search")
    fleet_code = CharFilter(lookup_expr="iexact")
    reg = CharFilter(lookup_expr="iexact")
    slug = CharFilter()
    operator = CharFilter()
    code = CharFilter("vehiclecode__code", label="Code")

    ordering = OrderingFilter(fields=(("id", "id"),))

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
    datetime = DateTimeFilter()


class StopFilter(FilterSet):
    class Meta:
        model = StopPoint
        fields = ["atco_code", "naptan_code", "stop_type"]


class ServiceFilter(FilterSet):
    operator = CharFilter()

    class Meta:
        model = Service
        fields = ["public_use", "mode", "slug"]


class OperatorFilter(FilterSet):
    class Meta:
        model = Operator
        fields = {
            "name": ["icontains"],
            "slug": ["exact"],
            "vehicle_mode": ["exact"],
            "region": ["exact"],
        }


class TripFilter(FilterSet):
    route = NumberFilter()
    operator = CharFilter()

    class Meta:
        model = Trip
        fields = ["ticket_machine_code", "vehicle_journey_code", "block"]


class LiveryFilter(FilterSet):
    vehicle__operator = CharFilter(label="Operator", distinct=True)

    class Meta:
        model = Livery
        fields = {
            "name": ["icontains"],
            "published": ["exact"],
            "id": ["exact", "in"],
        }


class VehicleTypeFilter(FilterSet):
    vehicle__operator = CharFilter(label="Operator", distinct=True)

    class Meta:
        model = VehicleType
        fields = {
            "id": ["exact", "in"],
            "name": ["icontains"],
        }
