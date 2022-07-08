from rest_framework import serializers
from busstops.models import Operator, Service, StopPoint
from bustimes.models import Trip, RouteLink
from vehicles.models import Vehicle, VehicleType, Livery, VehicleJourney


class VehicleSerializer(serializers.ModelSerializer):
    operator = serializers.SerializerMethodField()
    livery = serializers.SerializerMethodField()

    def get_operator(self, obj):
        if obj.operator_id:
            return {
                "id": obj.operator_id,
                "name": obj.operator.name,
                "parent": obj.operator.parent,
            }

    def get_livery(self, obj):
        if obj.colours or obj.livery_id:
            return {
                "id": obj.livery_id,
                "name": obj.livery_id and str(obj.livery),
                "left": obj.get_livery(),
                "right": obj.get_livery(90),
            }

    class Meta:
        model = Vehicle
        depth = 1
        fields = [
            "id",
            "fleet_number",
            "fleet_code",
            "reg",
            "vehicle_type",
            "livery",
            "branding",
            "operator",
            "garage",
            "name",
            "notes",
            "withdrawn",
        ]


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ["id", "name", "double_decker", "coach", "electric"]


class OperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operator
        fields = ["noc", "slug", "name", "region_id"]


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "slug", "line_name", "region_id", "mode"]


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = StopPoint
        fields = ["atco_code", "naptan_code", "common_name"]


class LiverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Livery
        fields = [
            "id",
            "name",
            "left_css",
            "right_css",
            "white_text",
            "text_colour",
            "stroke_colour",
        ]


class TripSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()
    times = serializers.SerializerMethodField()

    def get_service(self, obj):
        return {
            "id": obj.route.service_id,
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
            if stop_time.stop:
                stop = stop_time.stop
                name = stop.get_name_for_timetable()
                bearing = stop.get_heading()
                location = stop.latlong and stop.latlong.coords
            else:
                name = stop_time.stop_code
                bearing = None
                location = None
            yield {
                "stop": {
                    "atco_code": stop_time.stop_id,
                    "name": name,
                    "location": location,
                    "bearing": bearing,
                },
                "aimed_arrival_time": stop_time.arrival_time(),
                "aimed_departure_time": stop_time.departure_time(),
                "track": route_link and route_link.geometry.coords,
            }
            previous_stop_id = stop_time.stop_id

    class Meta:
        model = Trip
        fields = ["id", "service", "times"]


class VehicleJourneySerializer(serializers.ModelSerializer):
    vehicle = serializers.SerializerMethodField()

    def get_vehicle(self, obj):
        return {
            "id": obj.vehicle_id,
            "fleet_code": obj.vehicle.fleet_code,
            "reg": obj.vehicle.reg,
        }

    class Meta:
        model = VehicleJourney
        fields = ["id", "datetime", "vehicle", "trip_id", "route_name", "destination"]
