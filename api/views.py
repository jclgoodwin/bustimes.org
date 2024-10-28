from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import pagination, viewsets
from rest_framework.exceptions import APIException
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Q

from busstops.models import Operator, Service, StopPoint
from bustimes.models import StopTime, Trip
from bustimes.utils import contiguous_stoptimes_only
from vehicles.models import Livery, Vehicle, VehicleJourney, VehicleType

from . import filters, serializers


class BadException(APIException):
    status_code = 400


class LimitedPagination(pagination.LimitOffsetPagination):
    default_limit = 20
    max_limit = 20


class CursorPagination(pagination.CursorPagination):
    ordering = "-pk"
    page_size = 50
    max_page_size = 1000


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Vehicle.objects.select_related("vehicle_type", "livery", "operator", "garage")
        .annotate(special_features=ArrayAgg("features__name", filter=~Q(features=None)))
        .order_by("id")
    )
    serializer_class = serializers.VehicleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleFilter


class LiveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Livery.objects.order_by("id")
    serializer_class = serializers.LiverySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.LiveryFilter


class VehicleTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = serializers.VehicleTypeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleTypeFilter


class OperatorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Operator.objects.order_by("noc")
    serializer_class = serializers.OperatorSerializer
    pagination_class = CursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.OperatorFilter


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(current=True).prefetch_related("operator")
    serializer_class = serializers.ServiceSerializer
    pagination_class = CursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.ServiceFilter


class StopViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StopPoint.objects.order_by("atco_code").select_related("locality")
    serializer_class = serializers.StopSerializer
    pagination_class = CursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.StopFilter


class TripViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Trip.objects.select_related(
        "route__service", "operator"
    ).prefetch_related("notes")
    serializer_class = serializers.TripSerializer
    pagination_class = CursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.TripFilter

    def get_object(self):
        obj = super().get_object()
        trips = obj.get_trips()
        stops = (
            StopTime.objects.filter(trip__in=trips)
            .select_related("stop__locality")
            .defer(
                "stop__search_vector",
                "stop__locality__search_vector",
                "stop__locality__latlong",
            )
            .order_by("trip__start", "id")
        )
        if len(trips) > 1:
            stops = contiguous_stoptimes_only(stops, obj.id)
        obj.stops = stops
        return obj


class VehicleJourneyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleJourney.objects.select_related("vehicle")
    serializer_class = serializers.VehicleJourneySerializer
    pagination_class = CursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleJourneyFilter
