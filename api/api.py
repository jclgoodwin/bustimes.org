from django_filters.rest_framework import DjangoFilterBackend
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


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.select_related('operator', 'vehicle_type', 'livery').all()
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['operator', 'vehicle_type', 'livery', 'withdrawn', 'reg', 'fleet_code']


router = routers.DefaultRouter()
router.register('vehicles', VehicleViewSet)
