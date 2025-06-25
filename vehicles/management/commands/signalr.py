from http import HTTPStatus
import time
import json

import requests
from ciso8601 import parse_datetime
from django.contrib.gis.geos import GEOSGeometry

from busstops.models import DataSource, Service

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    def handle_item(self, item):
        parts = item.split("|")

        (
            dunno,
            vehicle_code,
            journey_code,
            route,
            direction,
            latitude,
            longitude,
            timestamp,
            bearing,
            mode,
        ) = parts

        recorded_at_time = parse_datetime(timestamp)

        if False:
            created = False
        else:
            fleet_number = int(vehicle_code) if vehicle_code.isdigit() else None
            vehicle, created = Vehicle.objects.select_related(
                "latest_journey"
            ).get_or_create(
                {
                    "operator_id": self.operator_id,
                    "fleet_code": str(fleet_number or vehicle_code),
                    "fleet_number": fleet_number,
                },
                source=self.source,
                code=vehicle_code,
            )

        journey = None
        if not created:
            if (
                vehicle.latest_journey
                and vehicle.latest_journey.code == journey_code
                and vehicle.latest_journey.route_name == route
                and vehicle.latest_journey.direction == direction
            ):
                journey = vehicle.latest_journey

        if not journey:
            try:
                service = (
                    Service.objects.filter(
                        current=True,
                        operator=self.operator_id,
                        source=self.timetable_source,
                        route__line_name__iexact=route,
                    )
                    .distinct()
                    .get()
                )
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                service = None
            else:
                if not service.tracking:
                    service.tracking = True
                    service.save(update_fields=["tracking"])

            journey = VehicleJourney(
                route_name=route,
                code=journey_code,
                source=self.source,
                direction=direction,
                vehicle=vehicle,
                service=service,
                datetime=recorded_at_time,
            )
            if journey.service:
                journey.trip = journey.get_trip(journey_code=journey_code)
            journey.save()

        if vehicle.latest_journey != journey:
            vehicle.latest_journey = journey
            vehicle.latest_journey_data = parts
            vehicle.save(update_fields=["latest_journey", "latest_journey_data"])

        if bearing == "-1":
            bearing = None

        location = VehicleLocation(
            GEOSGeometry(f"POINT({longitude} {latitude})"),
            heading=bearing,
        )
        location.id = vehicle.id
        location.datetime = recorded_at_time
        location.journey = journey

        self.to_save.append((location, vehicle))

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("source_name", type=str)

    def handle(self, source_name, *args, **options):
        self.source = DataSource.objects.get(name=source_name)
        hub_url = self.source.url

        self.timetable_source = DataSource.objects.get(name="IM")
        self.operator_id = "bus-vannin"
        self.region_id = "IM"

        session = requests.Session()

        negotiation = session.post(f"{hub_url}/negotiate?negotiateVersion=1").json()

        response = session.post(
            hub_url,
            params={
                "id": negotiation["connectionToken"],
            },
            data=json.dumps({"protocol": "json", "version": 1}) + "\x1e",
        )

        while (
            response := session.get(
                hub_url,
                params={
                    "id": negotiation["connectionToken"],
                    "_": int(time.time() * 1000),
                },
            )
        ).ok or response.status_code == HTTPStatus.GATEWAY_TIMEOUT:
            if response.ok:
                for part in response.content.split(b"\x1e"):
                    if part:
                        part = json.loads(part)
                        if "arguments" in part:
                            for argument in part["arguments"]:
                                for location in argument["locations"]:
                                    self.handle_item(location)
                            self.save()
