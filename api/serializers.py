from rest_framework import serializers

from busstops.models import Operator, Service, StopPoint
from bustimes.models import Garage, Note, Trip
from vehicles.models import Livery, Vehicle, VehicleJourney, VehicleType


class VehicleTypeSerializer(serializers.ModelSerializer):
    coach = serializers.SerializerMethodField()
    electric = serializers.SerializerMethodField()
    double_decker = serializers.SerializerMethodField()

    def get_coach(self, obj) -> bool:
        return obj.style == "coach"

    def get_electric(self, obj) -> bool:
        return obj.fuel == "electric"

    def get_double_decker(self, obj) -> bool:
        return obj.style == "double decker"

    class Meta:
        model = VehicleType
        fields = ["id", "name", "style", "fuel", "double_decker", "coach", "electric"]


class VehicleSerializer(serializers.ModelSerializer):
    operator = serializers.SerializerMethodField()
    livery = serializers.SerializerMethodField()
    vehicle_type = VehicleTypeSerializer()
    special_features = serializers.ListField()

    def get_operator(self, obj):
        if obj.operator_id:
            return {
                "id": obj.operator_id,
                "slug": obj.operator.slug,
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
            "slug",
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
            "special_features",
        ]


class OperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operator
        fields = [
            "noc",
            "slug",
            "name",
            "aka",
            "vehicle_mode",
            "region_id",
            "parent",
            "url",
            "twitter",
        ]


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id",
            "slug",
            "line_name",
            "description",
            "region_id",
            "mode",
            "operator",
        ]


class StopSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    long_name = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_name_for_timetable()

    def get_long_name(self, obj):
        return obj.get_long_name()

    def get_location(self, obj):
        if obj.latlong:
            return obj.latlong.coords

    def get_icon(self, obj):
        return obj.get_icon()

    class Meta:
        model = StopPoint
        fields = [
            "atco_code",
            "naptan_code",
            "common_name",
            "name",
            "long_name",
            "location",
            "indicator",
            "icon",
            "bearing",
            "heading",
            "stop_type",
            "bus_stop_type",
            "created_at",
            "modified_at",
            "active",
        ]


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


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = [
            "code",
            "text",
        ]


class GarageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Garage
        fields = [
            "code",
            "name",
        ]


class TripSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()
    operator = serializers.SerializerMethodField()
    times = serializers.SerializerMethodField()
    notes = NoteSerializer(many=True)

    @staticmethod
    def get_service(obj):
        return {
            "id": obj.route.service_id,
            "line_name": obj.route.line_name,
            "slug": obj.route.service and obj.route.service.slug,
            "mode": obj.route.service and obj.route.service.mode,
        }

    @staticmethod
    def get_operator(obj):
        if obj.operator:
            return {
                "noc": obj.operator_id,
                "name": obj.operator.name,
                "vehicle_mode": obj.operator.vehicle_mode,
                "slug": obj.operator.slug,
            }

    @staticmethod
    def get_times(obj):
        if not hasattr(obj, "stops"):
            return

        route_links = {
            (link.from_stop_id, link.to_stop_id): link
            for link in (
                obj.route.service.routelink_set.all() if obj.route.service else ()
            )
        }
        previous_stop_id = None

        for stop_time in obj.stops:
            route_link = route_links.get((previous_stop_id, stop_time.stop_id))
            if stop := stop_time.stop:
                name = stop.get_name_for_timetable()
                bearing = stop.get_heading()
                location = stop.latlong and stop.latlong.coords
                icon = stop.get_icon()
            else:
                name = stop_time.stop_code
                bearing = None
                location = None
                icon = None
            yield {
                "id": stop_time.id,
                "stop": {
                    "atco_code": stop_time.stop_id,
                    "name": name,
                    "location": location,
                    "bearing": bearing,
                    "icon": icon,
                },
                "aimed_arrival_time": stop_time.arrival_time(),
                "aimed_departure_time": stop_time.departure_time(),
                "track": route_link and route_link.geometry.coords,
                "timing_status": stop_time.timing_status,
                "pick_up": stop_time.pick_up,
                "set_down": stop_time.set_down,
                "expected_arrival_time": getattr(stop_time, "expected_arrival", None),
                "expected_departure_time": getattr(
                    stop_time, "expected_departure", None
                ),
            }
            previous_stop_id = stop_time.stop_id

    class Meta:
        model = Trip
        fields = [
            "id",
            "vehicle_journey_code",
            "ticket_machine_code",
            "block",
            "service",
            "operator",
            "notes",
            "times",
        ]


class VehicleJourneySerializer(serializers.ModelSerializer):
    vehicle = serializers.SerializerMethodField()

    def get_vehicle(self, obj):
        if obj.vehicle_id:
            return {
                "id": obj.vehicle_id,
                "slug": obj.vehicle.slug,
                "fleet_code": obj.vehicle.fleet_code,
                "reg": obj.vehicle.reg,
            }

    class Meta:
        model = VehicleJourney
        fields = [
            "id",
            "datetime",
            "vehicle",
            "route_name",
            "destination",
            "trip_id",
        ]
