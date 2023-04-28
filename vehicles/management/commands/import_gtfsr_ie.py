from datetime import datetime, timezone  # , timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry

# from django.utils.dateparse import parse_duration
from google.transit import gtfs_realtime_pb2

from busstops.models import DataSource, Service
from bustimes.models import Trip

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = "Realtime Transport Operators"
    previous_locations = {}

    def do_source(self):
        self.tzinfo = ZoneInfo("Europe/Dublin")
        self.source, _ = DataSource.objects.get_or_create(name=self.source_name)
        self.url = "https://api.nationaltransport.ie/gtfsr/v2/Vehicles"
        return self

    def get_datetime(self, item):
        return datetime.fromtimestamp(item.vehicle.timestamp, timezone.utc)

    def prefetch_vehicles(self, vehicle_codes):
        vehicles = self.vehicles.filter(source=self.source, code__in=vehicle_codes)
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_items(self):
        assert settings.NTA_API_KEY
        response = self.session.get(
            self.url, headers={"x-api-key": settings.NTA_API_KEY}, timeout=10
        )
        assert response.ok

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        items = []
        vehicle_codes = []

        # build list of vehicles that have moved
        for item in feed.entity:
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
                self.previous_locations[key] = value

        self.prefetch_vehicles(vehicle_codes)

        return items

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id

        if vehicle_code in self.vehicle_cache:
            return self.vehicle_cache[vehicle_code], False

        vehicle = Vehicle(
            code=vehicle_code, source=self.source, slug=f"ie-{vehicle_code.lower()}"
        )
        vehicle.save()

        return vehicle, True

    def get_journey(self, item, vehicle):
        # start_time = datetime.strptime(
        #    f"{item.vehicle.trip.start_date} 12:00:00",
        #    "%Y%m%d %H:%M:%S",
        # ) - timedelta(hours=12) + parse_duration(item.vehicle.trip.start_time)
        journey = VehicleJourney(
            code=item.vehicle.trip.trip_id,
            # datetime=start_time.replace(tzinfo=self.tzinfo)
        )

        if (
            (latest_journey := vehicle.latest_journey)
            # and latest_journey.datetime == journey.datetime
            and latest_journey.code == journey.code
        ):
            return latest_journey

        service = Service.objects.filter(
            route__source=self.source, route__code=item.vehicle.trip.route_id
        ).first()
        if service:
            trip = Trip.objects.filter(
                # route__source__in=self.source,
                route__service=service,
                ticket_machine_code=journey.code,
            ).first()

            journey.service = service
            journey.trip = trip

            journey.route_name = service.line_name

            if trip and trip.destination and trip.destination.locality:
                journey.destination = str(trip.destination.locality)
            if trip and trip.operator_id and not vehicle.operator_id:
                vehicle.operator_id = trip.operator_id
                vehicle.save(update_fields=["operator"])

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(
                f"POINT({item.vehicle.position.longitude} {item.vehicle.position.latitude})"
            ),
        )
