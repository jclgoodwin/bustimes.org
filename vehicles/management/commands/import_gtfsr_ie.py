from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.utils.dateparse import parse_duration
from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2

from busstops.models import DataSource, Service
from bustimes.models import Trip
from bustimes.utils import get_calendars

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand

occupancies = {
    0: "Empty",
    1: "Many seats available",
    2: "Few seats available",
    3: "Standing room only",
    4: "Crushed standing room only",
    5: "Full",
    6: "Not accepting passengers",
    7: "No data available",
    8: "Not boardable",
}


class Command(ImportLiveVehiclesCommand):
    source_name = "Realtime Transport Operators"
    vehicle_code_scheme = "NTA"

    def do_source(self):
        self.tzinfo = ZoneInfo("Europe/Dublin")
        self.source, _ = DataSource.objects.get_or_create(name=self.source_name)
        self.url = "https://api.nationaltransport.ie/gtfsr/v2/Vehicles"
        return self

    @staticmethod
    def get_datetime(item):
        return datetime.fromtimestamp(item.vehicle.timestamp, timezone.utc)

    @staticmethod
    def get_vehicle_identity(item):
        return item.vehicle.vehicle.id

    @staticmethod
    def get_journey_identity(item):
        return (
            item.vehicle.trip.route_id,
            item.vehicle.trip.trip_id,
            item.vehicle.trip.start_date,
        )

    @staticmethod
    def get_item_identity(item):
        return item.vehicle.timestamp

    def get_items(self):
        assert settings.NTA_API_KEY
        response = self.session.get(
            self.url, headers={"x-api-key": settings.NTA_API_KEY}, timeout=10
        )
        response.raise_for_status()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        return feed.entity

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id
        return Vehicle.objects.get_or_create(code=vehicle_code, source=self.source)

    def get_journey(self, item, vehicle):
        # GTFS spec for working out datetimes:
        start_date = datetime.strptime(
            f"{item.vehicle.trip.start_date} 12:00:00",
            "%Y%m%d %H:%M:%S",
        )
        start_time = parse_duration(item.vehicle.trip.start_time)
        start_date_time = (start_date + start_time - timedelta(hours=12)).replace(
            tzinfo=self.tzinfo
        )

        # assert not (datetime.fromtimestamp(item.vehicle.timestamp) - start_date_time > timedelta(hours=12))

        journey = VehicleJourney(code=item.vehicle.trip.trip_id)

        if (
            latest_journey := vehicle.latest_journey
        ) and latest_journey.code == journey.code:
            return latest_journey

        journey.datetime = start_date_time

        service = None
        services = Service.objects.filter(
            current=True,
            route__source=self.source,
            route__code=item.vehicle.trip.route_id,
        ).distinct()
        if not services:
            services = Service.objects.filter(
                current=True,
                route__source=self.source,
                route__trip__ticket_machine_code=journey.code,
            ).distinct()

        if services:
            service = services[0]

        trips = Trip.objects.filter(ticket_machine_code=journey.code)
        if service:
            trips = trips.filter(route__service=service)
        else:
            trips = trips.filter(route__source=self.source)

        trip = None

        if not (trips or service) and "_" in journey.code:
            route_suffix = item.vehicle.trip.route_id
            if "_" in route_suffix:
                route_suffix = route_suffix.split("_", 1)[1]
            try:
                service = Service.objects.filter(
                    route__source=self.source,
                    route__code__endswith=f"_{route_suffix}",
                ).get()
            except (Service.MultipleObjectsReturned, Service.DoesNotExist):
                pass

            trips = Trip.objects.filter(
                route__source=self.source,
                start=start_time,
                inbound=item.vehicle.trip.direction_id == 1,
            )
            if service:
                trips = trips.filter(route__service=service)

        if trips:
            if len(trips) > 1:
                calendar_ids = [trip.calendar_id for trip in trips]
                calendars = get_calendars(start_date, calendar_ids)
                trips = trips.filter(calendar__in=calendars)
                trip = trips.first()
            else:
                trip = trips[0]

        if service:
            journey.service = service

        if trip:
            if not journey.service:
                journey.service = trip.route.service
            journey.trip = trip

            if trip.destination:
                journey.destination = str(trip.destination.locality or trip.destination)
            if trip.operator_id and not vehicle.operator_id:
                vehicle.operator_id = trip.operator_id
                vehicle.save(update_fields=["operator"])

        if journey.service:
            journey.route_name = journey.service.line_name

        vehicle.latest_journey_data = json_format.MessageToDict(item)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            heading=item.vehicle.position.bearing or None,
            latlong=GEOSGeometry(
                f"POINT({item.vehicle.position.longitude} {item.vehicle.position.latitude})"
            ),
            occupancy=occupancies.get(item.vehicle.occupancy_status or None),
        )
