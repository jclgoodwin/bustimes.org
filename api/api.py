from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter
from rest_framework import routers, viewsets
from vehicles.models import Vehicle, Livery, VehicleType
from .serializers import VehicleSerializer, LiverySerializer, VehicleTypeSerializer


class VehicleFilter(FilterSet):
    search = CharFilter(method='search_filter', label='Search')

    def search_filter(self, queryset, name, value):
        value = value.upper()
        return queryset.filter(
            Q(reg=value) | Q(fleet_code=value)
        )

    class Meta:
        model = Vehicle
        fields = ['operator', 'vehicle_type', 'livery', 'withdrawn', 'reg', 'fleet_code']


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


router = routers.DefaultRouter()
router.register('vehicles', VehicleViewSet)
router.register('liveries', LiveryViewSet)
router.register('vehicletypes', VehicleTypeViewSet)
