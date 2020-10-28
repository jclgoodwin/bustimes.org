from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter
from rest_framework import routers, serializers, viewsets
from vehicles.models import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    operator = serializers.SerializerMethodField()
    livery = serializers.SerializerMethodField()

    def get_operator(self, obj):
        if obj.operator_id:
            return {
                'id': obj.operator_id,
                'name': obj.operator.name,
                'parent': obj.operator.parent,
            }

    def get_livery(self, obj):
        if obj.colours or obj.livery_id:
            return {
                'id': obj.livery_id,
                'name': obj.livery_id and str(obj.livery),
                'left': obj.get_livery(),
                'right': obj.get_livery(90)
            }

    class Meta:
        model = Vehicle
        depth = 1
        exclude = ['code', 'source', 'latest_location', 'features', 'colours']


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


router = routers.DefaultRouter()
router.register('vehicles', VehicleViewSet)
