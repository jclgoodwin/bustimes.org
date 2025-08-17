import functools
import json
from datetime import timedelta
from time import sleep

import ciso8601
from django.contrib.gis.geos import Point
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import OuterRef, Q
from django.utils import timezone
from requests import RequestException
from sql_util.utils import Exists

from busstops.models import Service
from bustimes.models import Calendar, Trip
from bustimes.utils import get_calendars

from ...models import VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand, redis_client


def parse_datetime(string):
    datetime = ciso8601.parse_datetime(string)
    return timezone.make_aware(datetime)


def get_trip_condition(date, time_since_midnight, calendar_ids=None):
    return Q(
        calendar__in=get_calendars(date, calendar_ids),
        start__lte=time_since_midnight + timedelta(minutes=5),
        end__gte=time_since_midnight - timedelta(minutes=30),
    )


class Command(ImportLiveVehiclesCommand):
    source_name = vehicle_code_scheme = "National Express"
    operators = [
        "NATX",
        "ie-1178",  # Dublin Express
    ]
    sleep = 3
    livery = 643

    @staticmethod
    def get_datetime(item):
        return parse_datetime(
            item["active_vehicle"]["last_update_time_formatted_local"]
        )

    def get_line_names(self):
        calendar_ids = list(
            Calendar.objects.filter(
                Exists(
                    "trip__route__service",
                    filter=Q(operator__in=self.operators),
                )
            ).values_list("id", flat=True)
        )

        now = self.source.datetime
        time_since_midnight = timedelta(
            hours=now.hour, minutes=now.minute, seconds=now.second
        )

        today = now.date()
        yesterday = today - timedelta(hours=24)
        time_since_yesterday_midnight = time_since_midnight + timedelta(hours=24)

        trips = Trip.objects.filter(
            get_trip_condition(now, time_since_midnight, calendar_ids)
            | get_trip_condition(yesterday, time_since_yesterday_midnight, calendar_ids)
        )
        has_trips = Exists(trips.filter(route__service=OuterRef("id")))

        tracking = Exists(
            VehicleJourney.objects.filter(
                service=OuterRef("id"),
                datetime__date__gte=yesterday,
                vehicle__isnull=False,
            )
        )

        line_names = Service.objects.filter(
            has_trips, ~tracking, operator__in=self.operators, current=True
        ).values_list("line_name", flat=True)
        assert line_names
        return line_names

    def create_vehicle_location(self, item):
        delay = item["tracking"]["current_delay_seconds"]
        if delay is not None:
            delay = timedelta(seconds=delay)
        return VehicleLocation(
            latlong=Point(
                item["active_vehicle"]["current_wgs84_longitude_degrees"],
                item["active_vehicle"]["current_wgs84_latitude_degrees"],
            ),
            heading=item["active_vehicle"]["current_forward_azimuth_degrees"],
            delay=delay,
        )

    def get_items(self):
        for line_name in self.get_line_names():
            line_name = line_name.upper()
            try:
                res = self.session.get(self.source.url.format(line_name), timeout=5)
                print(res.url)
                # print(res.text)
            except RequestException as e:
                print(e)
                continue
            if not res.ok:
                print(res.url, res)
                continue
            data = res.json()
            if "routes" not in data:
                print(res.url, data)
                continue
            for route in data["routes"]:
                for item in route["chronological_departures"]:
                    if item["active_vehicle"]:
                        yield (item)
            self.save()
            sleep(self.sleep)

    @functools.cache
    def get_service(self, line_name, class_code):
        operators = self.operators

        if class_code == "FALC":
            operators = ["SDVN"]

        services = Service.objects.filter(
            line_name__iexact=line_name, operator__in=operators, current=True
        )
        try:
            service = services.get()
        except Service.MultipleObjectsReturned:
            if class_code == "ST":
                service = services.get(operator="MEGA")
            elif class_code == "C":
                service = services.get(operator__in=["SCLK", "SCUL"])
            elif class_code == "DE":
                service = services.get(operator="ie-1178")
            else:
                return
        except Service.DoesNotExist:
            return

        if not service.tracking:
            service.tracking = True
            service.save(update_fields=["tracking"])
        return service

    def handle_item(self, item, now):
        route_name = item["trip"]["route_id"]
        service = self.get_service(item["trip"]["route_id"], item["trip"]["class_code"])
        departure_time = parse_datetime(item["trip"]["departure_time_formatted_local"])
        destination = item["trip"]["arrival_location_name"]

        journey = self.get_journey(route_name, service, departure_time, destination)

        updated_at = self.get_datetime(item)

        latest = redis_client.get(f"vehicle{journey.id}")
        if latest:
            latest = json.loads(latest)
            latest_datetime = ciso8601.parse_datetime(latest["datetime"])
            if latest_datetime >= updated_at:
                return

        if (now - updated_at).total_seconds() > 600:
            return

        location = self.create_vehicle_location(item)
        location.datetime = updated_at
        location.journey = journey
        location.id = journey.id
        pipeline = redis_client.pipeline(transaction=False)

        pipeline.rpush(*location.get_appendage())

        match item["trip"]["class_code"]:
            case "DE":  # Dublin Express
                livery = 2455
                operator_id = "ie-1178"
            case _:
                livery = self.livery
                operator_id = self.operators[0]

        pipeline.geoadd(
            "vehicle_location_locations",
            [location.latlong.x, location.latlong.y, journey.id],
        )
        if journey.service_id:
            pipeline.sadd(f"service{journey.service_id}vehicles", journey.id)
        pipeline.sadd(f"operator{operator_id}vehicles", journey.id)
        redis_json = location.get_redis_json()

        redis_json["vehicle"] = {
            "name": item["trip"]["operator_name"],
        }

        redis_json["vehicle"]["livery"] = livery

        if service:
            redis_json["service"]["url"] = service.get_absolute_url()
        redis_json = json.dumps(redis_json, cls=DjangoJSONEncoder)
        pipeline.set(f"vehicle{journey.id}", redis_json, ex=900)

        pipeline.execute()

    def handle_items(self, items):
        for item in items:
            self.handle_item(item, self.source.datetime)

    def update(self):
        self.handle_items(self.get_items())

    @functools.lru_cache
    def get_journey(self, route_name, service, departure_time, destination):
        journey = VehicleJourney.objects.filter(
            service=service,
            datetime=departure_time,
            destination=destination,
            vehicle=None,
            source=self.source,
        ).first()
        if not journey:
            journey = VehicleJourney(
                route_name=route_name,
                service=service,
                datetime=departure_time,
                destination=destination,
                source=self.source,
            )
            journey.trip = journey.get_trip(departure_time=departure_time)
            journey.save()
        return journey
