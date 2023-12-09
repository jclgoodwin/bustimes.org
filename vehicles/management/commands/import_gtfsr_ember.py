from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2

from busstops.models import DataSource
from bustimes.models import Trip

from ...models import Vehicle, VehicleJourney
from .import_gtfsr_ie import Command as BaseCommand


class Command(BaseCommand):
    source_name = "Ember"

    def do_source(self):
        # self.tzinfo = ZoneInfo("Europe/London")
        self.source, _ = DataSource.objects.get_or_create(name=self.source_name)
        self.url = "https://api.ember.to/v1/gtfs/realtime/"
        return self

    def get_items(self):
        response = self.session.get(self.url, timeout=10)
        assert response.ok

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        items = []
        vehicle_codes = []

        # build list of vehicles that have moved
        for item in feed.entity:
            if item.vehicle.vehicle.id:
                key = item.vehicle.vehicle.id
                value = (
                    item.vehicle.trip.route_id,
                    item.vehicle.trip.trip_id,
                    item.vehicle.trip.start_date,
                    item.vehicle.position.latitude,
                    item.vehicle.position.longitude,
                )
                if self.previous_locations.get(key) != value:
                    items.append(item)
                    vehicle_codes.append(key)
                    vehicle_codes.append(key.replace(" ", ""))
                    self.previous_locations[key] = value

        self.prefetch_vehicles(vehicle_codes)

        return items

    def prefetch_vehicles(self, vehicle_codes):
        vehicles = self.vehicles.filter(operator="EMBR", code__in=vehicle_codes)
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id
        vehicle = self.vehicle_cache.get(vehicle_code)

        if not vehicle:
            vehicle = self.vehicle_cache.get(vehicle_code.replace(" ", ""))
            if vehicle:
                vehicle.code = vehicle_code
                vehicle.save(update_fields=["code"])
                self.vehicle_cache[vehicle_code] = vehicle

        if vehicle:
            return vehicle, False  # not created

        vehicle = Vehicle(code=vehicle_code, operator_id="EMBR", source=self.source)
        vehicle.save()

        return vehicle, True  # created

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(code=item.vehicle.trip.trip_id)

        if (
            latest_journey := vehicle.latest_journey
        ) and latest_journey.code == journey.code:
            return latest_journey

        trip = Trip.objects.get(
            route__source=self.source, vehicle_journey_code=journey.code
        )
        journey.trip = trip
        journey.service = trip.route.service

        journey.route_name = journey.service.line_name
        journey.destination = str(trip.destination.locality)

        vehicle.latest_journey_data = json_format.MessageToDict(item)

        return journey
