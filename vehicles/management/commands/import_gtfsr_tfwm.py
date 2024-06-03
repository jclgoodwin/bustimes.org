# from urllib.parse import urlencode

import gtfs_kit
from django.conf import settings
from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2

from busstops.models import DataSource

from ...models import Vehicle, VehicleJourney
from .import_gtfsr_ie import Command as BaseCommand

# from bustimes.download_utils import download_if_changed


class Command(BaseCommand):
    source_name = "TfWM"
    url = "http://api.tfwm.org.uk/gtfs/vehicle_positions"

    def do_source(self):
        self.source = DataSource.objects.get(name=self.source_name)

        # static GTFS schedule data:
        # url = (
        #     "http://api.tfwm.org.uk/gtfs/tfwm_gtfs.zip"
        #     + "?"
        #     + urlencode(self.source.settings)
        # )
        path = settings.DATA_DIR / "tfwm_gtfs.zip"

        # download_if_changed(path, url)

        self.feed = gtfs_kit.read_feed(path, dist_units="km")

        return self

    def get_items(self):
        response = self.session.get(self.url, params=self.source.settings, timeout=10)
        print(response.url)
        assert response.ok

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        items = []
        vehicle_codes = []

        # stop_notes = {}

        # print(feed)

        # build list of vehicles that have moved
        for item in feed.entity:
            assert item.HasField("vehicle")
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
                if key.startswith("TNXB-"):
                    vehicle_codes.append(key.removeprefix("TNXB-"))
                self.previous_locations[key] = value

        self.prefetch_vehicles(vehicle_codes)

        return items

    def prefetch_vehicles(self, vehicle_codes):
        vehicles = self.vehicles.filter(operator="TNXB", code__in=vehicle_codes)
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id
        print(vehicle_code)
        vehicle = self.vehicle_cache.get(vehicle_code)

        if not vehicle and vehicle_code.startswith("TNXB-"):
            vehicle = self.vehicle_cache.get(vehicle_code.removeprefix("TNXB-"))

        if not vehicle:
            vehicle = Vehicle.objects.create(code=vehicle_code, operator_id="TNXB")
            return vehicle, True

        return vehicle, False  # not created

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(code=item.vehicle.trip.trip_id)

        if (
            latest_journey := vehicle.latest_journey
        ) and latest_journey.code == journey.code:
            return latest_journey

        print(item)
        #     try:
        #         trip = Trip.objects.get(operator="EMBR", vehicle_journey_code=journey.code)
        #     except Trip.DoesNotExist:
        #         pass
        #     else:
        #         journey.trip = trip

        #         journey.datetime = (
        #             datetime.strptime(
        #                 f"{item.vehicle.trip.start_date} 12", "%Y%m%d %H"
        #             ).replace(tzinfo=self.tzinfo)
        #             - timedelta(hours=12)
        #             + trip.start
        #         )

        # journey.service = trip.route.service

        #         journey.route_name = journey.service.line_name
        #         if trip.destination_id:
        #             journey.destination = str(trip.destination.locality)

        vehicle.latest_journey_data = json_format.MessageToDict(item)

        return journey
