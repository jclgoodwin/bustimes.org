from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, pagination
from rest_framework.exceptions import APIException

from busstops.models import Operator, Service, StopPoint
from bustimes.models import Trip
from vehicles.models import Vehicle, Livery, VehicleType, VehicleJourney
from . import filters, serializers


class BadException(APIException):
    status_code = 400


class LimitedPagination(pagination.LimitOffsetPagination):
    default_limit = 20
    max_limit = 20


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.select_related(
        "operator", "vehicle_type", "livery"
    ).order_by("id")
    serializer_class = serializers.VehicleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleFilter


class LiveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Livery.objects.order_by("id")
    serializer_class = serializers.LiverySerializer


class VehicleTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = serializers.VehicleTypeSerializer


class OperatorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Operator.objects.order_by("noc")
    serializer_class = serializers.OperatorSerializer


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(current=True)
    serializer_class = serializers.ServiceSerializer


class StopViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StopPoint.objects.order_by("atco_code")
    serializer_class = serializers.StopSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.StopFilter


class TripViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Trip.objects.select_related("route__service").prefetch_related(
        "stoptime_set__stop__locality"
    )
    serializer_class = serializers.TripSerializer
    pagination_class = LimitedPagination

    def list(self, request):
        raise BadException(detail="Listing all trips is not allowed")


class VehicleJourneyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleJourney.objects.select_related("vehicle")
    serializer_class = serializers.VehicleJourneySerializer
    pagination_class = LimitedPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleJourneyFilter

    def list(self, request):
        if not (
            request.GET.get("trip")
            or request.GET.get("vehicle")
            or request.GET.get("service")
        ):
            raise BadException(
                detail="Listing all journeys without filtering by trip, vehicle, or service is not allowed"
            )
        return super().list(request)
