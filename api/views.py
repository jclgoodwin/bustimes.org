import struct
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import pagination, viewsets
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Q

from vehicles.time_aware_polyline import encode_time_aware_polyline

from busstops.models import Operator, Service, StopPoint
from bustimes.models import StopTime, Trip
from bustimes.utils import contiguous_stoptimes_only
from vehicles.models import Livery, Vehicle, VehicleJourney, VehicleType
from vehicles.utils import redis_client

from sql_util.utils import Exists

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
    queryset = (
        Operator.objects.filter(
            Exists("vehicle") | Exists("service", filter=Q(service__current=True))
        )
        .order_by("noc")
        .defer("address", "email", "phone", "search_vector")
    )
    serializer_class = serializers.OperatorSerializer
    pagination_class = CursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.OperatorFilter


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(current=True).prefetch_related("operator")
    serializer_class = serializers.ServiceSerializer
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

    @staticmethod
    def get_stops(obj):
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
        return stops

    def get_object(self):
        obj = super().get_object()
        obj.stops = self.get_stops(obj)
        return obj


class VehicleJourneyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleJourney.objects.select_related("vehicle")
    serializer_class = serializers.VehicleJourneySerializer
    pagination_class = CursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleJourneyFilter

    def retrieve(self, request, *args, pk, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        extra_data = {}

        if instance.trip:
            instance.trip.stops = TripViewSet.get_stops(instance.trip)
            extra_data["times"] = serializers.TripSerializer().get_times(instance.trip)

        if redis_client:
            locations = redis_client.lrange(instance.get_redis_key(), 0, -1)
            locations = [
                struct.unpack("I 2f ?h ?h", location) for location in locations
            ]
            polyline = encode_time_aware_polyline(
                [[lat, lng, time] for time, lat, lng, _, _, _, _ in locations]
            )
            extra_data["time_aware_polyline"] = polyline

        extra_data["service"] = {
            "id": instance.service_id,
            "slug": instance.service.slug,
        }

        return Response(serializer.data | extra_data)
