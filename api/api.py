from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter
from rest_framework import routers, viewsets
from rest_framework.exceptions import NotFound
from bustimes.models import Trip
from vehicles.models import Vehicle, Livery, VehicleType
from .serializers import VehicleSerializer, LiverySerializer, VehicleTypeSerializer, TripSerializer


class VehicleFilter(FilterSet):
    search = CharFilter(method='search_filter', label='Search')
    fleet_code = CharFilter(lookup_expr='iexact')
    reg = CharFilter(lookup_expr='iexact')

    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(reg__iexact=value) | Q(fleet_code__iexact=value)
        )

    class Meta:
        model = Vehicle
        fields = ['id', 'operator', 'vehicle_type', 'livery', 'withdrawn']


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.select_related('operator', 'vehicle_type', 'livery').order_by('id')
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = VehicleFilter


class LiveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Livery.objects.all()
    serializer_class = LiverySerializer


class VehicleTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer


class TripViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Trip.objects.select_related('route').prefetch_related('stoptime_set__stop__locality')
    serializer_class = TripSerializer

    def list(self, request):
        raise NotFound


router = routers.DefaultRouter()
router.register('vehicles', VehicleViewSet)
router.register('liveries', LiveryViewSet)
router.register('vehicletypes', VehicleTypeViewSet)
router.register('trips', TripViewSet)
