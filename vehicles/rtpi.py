from datetime import timedelta
from itertools import pairwise

from ciso8601 import parse_datetime
from django.contrib.gis.geos import LineString, Point
from django.utils import timezone

from bustimes.models import RouteLink, StopTime, Trip
from vehicles.utils import calculate_bearing


def get_progress(item):
    point = Point(*item["coordinates"])

    trips = Trip.objects.get(id=item["trip_id"]).get_trips()

    stop_times = (
        StopTime.objects.filter(trip__in=trips)
        .filter(stop__latlong__isnull=False)
        .select_related("stop")
        .order_by("trip__start", "id")
    )

    if not stop_times:
        return

    pairs = [
        (a, b, LineString([a.stop.latlong, b.stop.latlong]))
        for a, b in pairwise(stop_times)
    ]

    pairs.sort(key=lambda pair: pair[2].distance(point))

    closest = pairs[0]

    if len(pairs) >= 2 and item["heading"] is not None:

        vehicle_heading = int(item["heading"])

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

    line_string = closest[2]
    if "service_id" in item:
        try:
            line_string = RouteLink.objects.get(
                service=item["service_id"],
                from_stop=closest[0].stop_id,
                to_stop=closest[1].stop_id,
            ).geometry
        except RouteLink.DoesNotExist:
            pass

    progress = line_string.project_normalized(point)

    return closest[0], closest[1], progress


def add_progress_and_delay(item):
    prev_stop, next_stop, progress = get_progress(item)

    item["progress"] = {
        "id": prev_stop.id,
        "sequence": prev_stop.sequence,
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

    try:
        expected_time = prev_time + (next_time - prev_time) * progress
    except ValueError:
        pass
    else:
        delay = int((when - expected_time).total_seconds())
        item["delay"] = delay
