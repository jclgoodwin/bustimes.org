import functools
import json
import ciso8601
from datetime import timedelta
from time import sleep
from requests import RequestException
from django.contrib.gis.geos import Point
from django.core.serializers.json import DjangoJSONEncoder
from busstops.models import Service
from .import_nx import Command as NatExpCommand, parse_datetime
from ...models import VehicleJourney, VehicleLocation
from ...utils import redis_client


class Command(NatExpCommand):
    source_name = "Megabus"
    url = ""
    operators = ["MEGA"]
    sleep = 10
    livery = 910

    def get_items(self):
        for line_name in self.get_line_names():
            line_name = line_name.upper()
            try:
                res = self.session.get(self.source.url.format(line_name), timeout=5)
            except RequestException as e:
                print(e)
                continue
            if not res.ok:
                print(res.url, res)
                continue
            for item in res.json()["routes"][0]["chronological_departures"]:
                if item["active_vehicle"]:
                    yield (item)
            self.save()
            sleep(self.sleep)

    @functools.cache
    def get_service(self, line_name):
        service = Service.objects.get(
            line_name__iexact=line_name, operator__in=self.operators, current=True
        )
        if not service.tracking:
            service.tracking = True
            service.save(update_fields=["tracking"])
        return service

    def handle_item(self, item, now):
        service = self.get_service(item["trip"]["route_id"])
        departure_time = parse_datetime(item["trip"]["departure_time_formatted_local"])
        destination = item["trip"]["arrival_location_name"]

        journey = VehicleJourney.objects.filter(
            service=service, datetime=departure_time, destination=destination
        ).first()

        if not journey:
            journey = VehicleJourney(
                source=self.source,
                service=service,
                datetime=departure_time,
                destination=destination,
            )
            journey.trip = journey.get_trip(departure_time=departure_time)
            journey.save()
        journey.route_name = item["trip"]["route_id"]

        updated_at = parse_datetime(
            item["active_vehicle"]["last_update_time_formatted_local"]
        )

        latest = redis_client.get(f"vehicle{journey.id}")
        if latest:
            latest = json.loads(latest)
            latest_datetime = ciso8601.parse_datetime(latest["datetime"])
            if latest_datetime >= updated_at:
                return

        delay = item["tracking"]["current_delay_seconds"]
        location = VehicleLocation(
            latlong=Point(
                item["active_vehicle"]["current_wgs84_longitude_degrees"],
                item["active_vehicle"]["current_wgs84_latitude_degrees"],
            ),
            heading=item["active_vehicle"]["current_forward_azimuth_degrees"],
            early=-timedelta(seconds=delay) if delay is not None else None,
        )
        location.datetime = updated_at
        location.journey = journey
        location.id = journey.id
        pipeline = redis_client.pipeline(transaction=False)

        pipeline.rpush(*location.get_appendage())

        pipeline.geoadd(
            "vehicle_location_locations",
            [location.latlong.x, location.latlong.y, journey.id],
        )
        pipeline.sadd(f"service{journey.service_id}vehicles", journey.id)
        redis_json = location.get_redis_json()
        redis_json["vehicle"] = {"livery": self.livery}
        redis_json["service"]["url"] = service.get_absolute_url()
        redis_json = json.dumps(redis_json, cls=DjangoJSONEncoder)
        pipeline.set(f"vehicle{journey.id}", redis_json, ex=900)

        pipeline.execute()
