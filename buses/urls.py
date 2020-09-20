from django.urls import include, path
from django.contrib import admin
from rest_framework import routers, serializers, viewsets
from vehicles.models import Vehicle, VehicleType


class VehicleSerializer(serializers.HyperlinkedModelSerializer):
    operator = serializers.SerializerMethodField()
    livery = serializers.SerializerMethodField()

    def get_operator(self, obj):
        return obj.operator_id and {
            'id': obj.operator_id,
            'name': obj.operator.name,
            'parent': obj.operator.parent,
        }

    def get_livery(self, obj):
        return {
            'name': obj.livery and str(obj.livery),
            'left': obj.get_livery(),
            'right': obj.get_livery(270)
        }

    class Meta:
        model = Vehicle
        depth = 1
        exclude = ['code', 'source', 'latest_location', 'features', 'colours']


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = '__all__'


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.select_related('operator', 'vehicle_type', 'livery').all()
    serializer_class = VehicleSerializer


class VehicleTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer


router = routers.DefaultRouter()
router.register('vehicles', VehicleViewSet)
router.register('types', VehicleTypeViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('api/', include(router.urls)),
    path('', include('busstops.urls')),
]


handler404 = 'busstops.views.not_found'
