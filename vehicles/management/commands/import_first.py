import asyncio
import json
from datetime import datetime
from uuid import uuid4

import requests
import websockets
from asgiref.sync import sync_to_async
from ciso8601 import parse_datetime
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Point
from django.utils import timezone

from busstops.models import DataSource, Operator, Service

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    def handle_item(self, item, operator):
        vehicle_id = item["status"]["vehicle_id"]
        parts = vehicle_id.split("-")

        vehicle = parts[6]

        try:
            vehicle = self.vehicles.get(operator__parent="First", code=vehicle)
            created = False
        except (Vehicle.MultipleObjectsReturned, Vehicle.DoesNotExist):
            defaults = {"source": self.source}
            if vehicle.isdigit():
                defaults["fleet_number"] = defaults["fleet_code"] = vehicle
            vehicle, created = self.vehicles.get_or_create(
                defaults, operator_id=operator, code=vehicle
            )

        recorded_at_time = parse_datetime(item["status"]["recorded_at_time"])
        # if not created and vehicle.latest_journey and recorded_at_time <= vehicle.latest_location.datetime:
        #     return

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
                service = Service.objects.get(
                    current=True, operator=operator, line_name__iexact=item["line_name"]
                )
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, operator, item["line_name"])
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
                direction=item["dir"],
                datetime=departure_time,
                source=self.source,
                destination=destination,
                vehicle=vehicle,
                service=service,
            )
            journey.trip = journey.get_trip()
            journey.save()
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

    @sync_to_async
    def handle_data(self, data, operator):
        for item in data["params"]["resource"]["member"]:
            self.handle_item(item, operator)
        self.save()

    @staticmethod
    def get_extent(operator):
        services = Service.objects.filter(operator=operator, current=True)
        return services.aggregate(Extent("geometry"))["geometry__extent"]

    async def sock_it(self, operator, extent):

        socket_info = requests.get(
            self.source.url,
            headers={
                "x-app-key": "b05fbe23a091533ea3efbc28321f96a1cf3448c1",
            },
        ).json()

        min_lon, min_lat, max_lon, max_lat = extent
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "method": "configuration",
                "params": {
                    # "operator": "ACAH",
                    # "service": "X1",
                    "min_lon": min_lon,
                    "max_lon": max_lon,
                    "min_lat": min_lat,
                    "max_lat": max_lat,
                },
            }
        )

        async with websockets.connect(
            socket_info["data"]["url"],
            extra_headers={
                "Authorization": f'Bearer {socket_info["data"]["access-token"]}'
            },
        ) as websocket:
            await websocket.send(message)

            response = await websocket.recv()
            ok = True

            while ok:
                response = await websocket.recv()

                data = json.loads(response)
                try:
                    await self.handle_data(data, operator)
                    count = len(data["params"]["resource"]["member"])
                    if count >= 50:
                        print(operator, count)
                        ok = False
                except (KeyError, ValueError) as e:
                    print(e)

    def handle(self, *args, **options):
        self.source = DataSource.objects.update_or_create(
            {
                "url": "https://prod.mobileapi.firstbus.co.uk/api/v2/bus/service/socketInfo"
            },
            name="First",
        )[0]

        operator = Operator.objects.get(name="Aircoach")

        extent = self.get_extent(operator)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.sock_it(operator, extent))
        loop.close()
