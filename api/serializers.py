from rest_framework import serializers
from bustimes.models import Trip, RouteLink
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
        fields = ['id', 'fleet_number', 'fleet_code', 'reg', 'vehicle_type', 'livery',
                  'branding', 'operator', 'name', 'notes', 'withdrawn']


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'coach', 'double_decker']


class LiverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Livery
        fields = ['id', 'name', 'left_css', 'right_css']


class TripSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()
    times = serializers.SerializerMethodField()

    def get_service(self, obj):
        return {
            "line_name": obj.route.service.line_name,
        }

    def get_times(self, obj):
        route_links = RouteLink.objects.filter(service=obj.route.service_id)
        route_links = {
            (link.from_stop_id, link.to_stop_id): link for link in route_links
        }
        previous_stop_id = None
        for stop_time in obj.stoptime_set.all():
            route_link = route_links.get((previous_stop_id, stop_time.stop_id))
            yield {
                "stop": {
                    "atco_code": stop_time.stop_id,
                    "name": stop_time.stop.get_name_for_timetable() if stop_time.stop else stop_time.stop_code,
                    "location": stop_time.stop and stop_time.stop.latlong and stop_time.stop.latlong.coords,
                    "bearing": stop_time.stop and stop_time.stop.get_heading(),
                },
                "aimed_arrival_time": stop_time.arrival_time(),
                "aimed_departure_time": stop_time.departure_time(),
                "track": route_link and route_link.geometry.coords
            }
            previous_stop_id = stop_time.stop_id

    class Meta:
        model = Trip
        fields = ['id', 'service', 'times']
