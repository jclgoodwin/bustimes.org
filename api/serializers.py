from rest_framework import serializers
from vehicles.models import Vehicle, VehicleType, Livery


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
        exclude = ['code', 'source', 'latest_location', 'latest_journey', 'features', 'colours']


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'coach', 'double_decker']


class LiverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Livery
        fields = ['id', 'name', 'left_css', 'right_css']
