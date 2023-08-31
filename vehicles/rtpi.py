from datetime import timedelta
from itertools import pairwise

import shapely
from ciso8601 import parse_datetime
from django.utils import timezone

from bustimes.models import StopTime
from vehicles.utils import calculate_bearing


def get_progress(item):
    point = shapely.Point(*item["coordinates"])

    stop_times = (
        StopTime.objects.filter(trip=item["trip_id"])
        .filter(stop__latlong__isnull=False)
        .select_related("stop")
    )

    if not stop_times:
        return

    pairs = [
        (a, b, shapely.LineString([a.stop.latlong, b.stop.latlong]))
        for a, b in pairwise(stop_times)
    ]

    pairs.sort(key=lambda pair: pair[2].distance(point))

    closest = pairs[0]

    if len(pairs) >= 2 and item["heading"] is not None:

        vehicle_heading = item["heading"]

        route_bearing = calculate_bearing(
            closest[0].stop.latlong, closest[1].stop.latlong
        )

        difference = (vehicle_heading - route_bearing + 180) % 360 - 180
        if not (-90 < difference < 90):
            # bus seems to be heading the wrong way - does the bus go both ways on this road?
            # try the next closest pair of stops:
            route_bearing = calculate_bearing(
                pairs[1][0].stop.latlong, pairs[1][1].stop.latlong
            )

            difference = (vehicle_heading - route_bearing + 180) % 360 - 180
            if -90 < difference < 90:
                closest = pairs[1]

    progress = closest[2].project(point, normalized=True)

    return closest, progress


def add_progress_and_delay(item):
    (prev_stop, next_stop, line_string), progress = get_progress(item)

    item["progress"] = {
        "prev_stop": prev_stop.stop_id,
        "next_stop": next_stop.stop_id,
        "progress": round(progress, 3),
    }
    when = parse_datetime(item["datetime"])
    when = timezone.localtime(when)
    when = timedelta(hours=when.hour, minutes=when.minute, seconds=when.second)

    prev_time = prev_stop.departure_or_arrival()
    next_time = next_stop.arrival_or_departure()

    # correct for timetable times being > 24 hours:
    if when - prev_time < -timedelta(hours=12):
        when += timedelta(hours=24)

    expected_time = prev_time + (next_time - prev_time) * progress
    delay = int((when - expected_time).total_seconds())

    item["delay"] = delay
