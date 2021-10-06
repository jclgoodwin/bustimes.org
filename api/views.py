from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, pagination

from bustimes.models import Trip
from vehicles.models import Vehicle, Livery, VehicleType, VehicleJourney
from . import filters, serializers


class LimitedPagination(pagination.LimitOffsetPagination):
    default_limit = 20
    max_limit = 20


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.select_related('operator', 'vehicle_type', 'livery').order_by('id')
    serializer_class = serializers.VehicleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleFilter


class LiveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Livery.objects.all()
    serializer_class = serializers.LiverySerializer


class VehicleTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = serializers.VehicleTypeSerializer


class TripViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Trip.objects.select_related('route__service').prefetch_related('stoptime_set__stop__locality')
    serializer_class = serializers.TripSerializer
    pagination_class = LimitedPagination


class VehicleJourneyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleJourney.objects.select_related('vehicle')
    serializer_class = serializers.VehicleJourneySerializer
    pagination_class = LimitedPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VehicleJourneyFilter
