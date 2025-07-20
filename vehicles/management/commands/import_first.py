import asyncio
import json
from datetime import datetime
from uuid import uuid4

import requests
from asgiref.sync import sync_to_async
from ciso8601 import parse_datetime
from django.db.models import Q
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Point
from django.utils import timezone
from websockets.asyncio.client import connect

from busstops.models import DataSource, Operator, Service

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    def handle_item(self, item, vehicle):
        journey_code, vehicle_code = self.split_vehicle_id(item)

        recorded_at_time = parse_datetime(item["status"]["recorded_at_time"])

        if vehicle_code in self.cache and self.cache[vehicle_code] == recorded_at_time:
            return
        self.cache[vehicle_code] = recorded_at_time

        if vehicle:
            created = False
        else:
            fleet_number = int(vehicle_code) if vehicle_code.isdigit() else None
            vehicle, _ = Vehicle.objects.get_or_create(
                {
                    "source": self.source,
                    "fleet_code": str(fleet_number or ""),
                    "fleet_number": fleet_number,
                },
                operator_id=item["operator"],
                code=vehicle_code,
            )
            created = True

        # origin aimed departure time
        departure_time = item["stops"][0]["date"] + " " + item["stops"][0]["time"]
        departure_time = timezone.make_aware(
            datetime.strptime(departure_time, "%Y-%m-%d %H:%M")
        )

        if not created:
            if (
                vehicle.latest_journey
                and vehicle.latest_journey.datetime == departure_time
            ):
                journey = vehicle.latest_journey
            else:
                journey = VehicleJourney.objects.filter(
                    vehicle=vehicle, datetime=departure_time
                ).first()
        else:
            journey = None

        if not journey:
            try:
                service = (
                    Service.objects.filter(
                        current=True,
                        operator=item["operator"],
                        route__line_name__iexact=item["line_name"],
                    )
                    .distinct()
                    .get()
                )
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item["operator"], item["line_name"])
                service = None
            if service and not service.tracking:
                service.tracking = True
                service.save(update_fields=["tracking"])

            destination = item["stops"][-1]
            if destination["locality"]:
                destination = destination["locality"].split(", ", 1)[0]
            else:
                destination = destination["stop_name"].split(", ", 1)[0]
            journey = VehicleJourney(
                route_name=item["line_name"],
                code=journey_code,
                datetime=departure_time,
                source=self.source,
                destination=destination,
                vehicle=vehicle,
                service=service,
            )
            journey.trip = journey.get_trip(
                departure_time=departure_time,
                destination_ref=item["stops"][-1]["atcocode"],
            )
            journey.save()

        if vehicle.latest_journey != journey:
            vehicle.latest_journey = journey
            vehicle.latest_journey_data = item
            vehicle.save(update_fields=["latest_journey", "latest_journey_data"])

        heading = item["status"]["bearing"]
        if heading == -1:
            heading = None

        location = VehicleLocation(
            latlong=Point(*item["status"]["location"]["coordinates"]),
            heading=heading,
        )
        location.id = vehicle.id
        location.datetime = recorded_at_time
        location.journey = journey

        self.to_save.append((location, vehicle))

    @staticmethod
    def split_vehicle_id(item: dict) -> (str, str):
        prefix = f"{item['operator']}-{item['dir']}-"
        suffix = f"-{item['line_name']}"
        vehicle = item["status"]["vehicle_id"]

        assert vehicle.startswith(prefix)
        assert vehicle.endswith(suffix)
        vehicle = vehicle.removesuffix(suffix).removeprefix(prefix)
        journey, vehicle = vehicle[11:].split("-", 1)
        return journey, vehicle

    @sync_to_async
    def handle_data(self, data):
        if "params" in data:
            items = data["params"]["resource"]["member"]
        else:
            items = data["member"]

        vehicle_codes = [self.split_vehicle_id(item)[1] for item in items]
        print(vehicle_codes)
        vehicles = Vehicle.objects.filter(
            operator__parent="First", code__in=vehicle_codes
        )
        vehicles = vehicles.select_related("latest_journey")
        vehicles = {vehicle.code: vehicle for vehicle in vehicles}
        for i, item in enumerate(items):
            self.handle_item(item, vehicles.get(vehicle_codes[i]))
        self.save()

    @staticmethod
    def get_extent(operator):
        services = Service.objects.filter(operator=operator, current=True)
        return services.aggregate(Extent("geometry"))["geometry__extent"]

    async def sock_it(self, extent):
        socket_info = requests.get(self.source.url, headers=self.source.settings).json()

        min_lon, min_lat, max_lon, max_lat = extent

        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "method": "configuration",
                "params": {
                    # "operator": "ACAH",
                    # "stop_of_interest": "2900N12216",
                    "min_lon": min_lon,
                    "max_lon": max_lon,
                    "min_lat": min_lat,
                    "max_lat": max_lat,
                },
            }
        )

        async with connect(
            socket_info["data"]["url"],
            max_size=40000000,
            additional_headers={
                "Authorization": f"Bearer {socket_info['data']['access-token']}"
            },
        ) as websocket:
            await websocket.send(message)

            response = await websocket.recv()
            ok = True

            while ok:
                response = await websocket.recv()

                data = json.loads(response)
                try:
                    await self.handle_data(data)
                    count = len(data["params"]["resource"]["member"])
                    print(count)
                except (KeyError, ValueError) as e:
                    print(e)

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("operator_name", type=str)

    def handle(self, operator_name, *args, **options):
        self.source = DataSource.objects.get(name="First")

        self.cache = {}
        operator = Operator.objects.get(Q(name=operator_name) | Q(noc=operator_name))

        extent = self.get_extent(operator)
        asyncio.run(self.sock_it(extent))
