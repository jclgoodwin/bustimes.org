# "Real Time Passenger Information"-ish stuff - calculating delays etc

from datetime import timedelta
from itertools import pairwise

from ciso8601 import parse_datetime
from django.contrib.gis.geos import LineString, Point
from django.utils import timezone

from bustimes.models import RouteLink, StopTime, Trip
from bustimes.utils import contiguous_stoptimes_only
from vehicles.utils import calculate_bearing


def get_stop_times(item):
    trip = Trip.objects.get(pk=item["trip_id"])
    trips = trip.get_trips()

    stop_times = (
        StopTime.objects.filter(trip__in=trips)
        .filter(stop__latlong__isnull=False)
        .select_related("stop")
        .only("arrival", "departure", "stop__latlong")
        .order_by("trip__start", "id")
    )

    if len(trips) > 1:
        return contiguous_stoptimes_only(stop_times, trip.id)

    return stop_times


class Progress:
    def __init__(self, stop_times, prev_stop_time, next_stop_time, progress, distance):
        self.stop_times = list(stop_times)
        self.sequence = self.stop_times.index(prev_stop_time)
        self.prev_stop_time = prev_stop_time
        self.next_stop_time = next_stop_time
        self.progress = round(progress, 3)
        self.distance = distance

    def to_json(self):
        return {
            "id": self.prev_stop_time.id,
            "sequence": self.sequence,
            "prev_stop": self.prev_stop_time.stop_id,
            "next_stop": self.next_stop_time.stop_id,
            "progress": self.progress,
        }


def get_progress(item, stop_time=None):
    point = Point(*item["coordinates"])

    if stop_time:
        stop_times = stop_time.trip.stoptime_set.all()  # prefetched earlier
    else:
        try:
            stop_times = get_stop_times(item)
        except Trip.DoesNotExist:
            return

    pairs = [
        (a, b, LineString([a.stop.latlong, b.stop.latlong]))
        for a, b in pairwise(stop_times)
    ]

    # compute distances:
    pairs = ((pair, pair[2].distance(point)) for pair in pairs)
    # filter out pairs further about than 1.1 km:
    nearby_pairs = [pair for pair in pairs if pair[1] < 0.01]

    if not nearby_pairs:
        return

    nearby_pairs.sort(key=lambda pair: pair[1])

    closest, distance = nearby_pairs[0]

    if len(nearby_pairs) >= 2 and item["heading"] is not None:
        vehicle_heading = int(item["heading"])

        # TODO: use RouteLink if there is one
        route_bearing = calculate_bearing(
            closest[0].stop.latlong, closest[1].stop.latlong
        )

        difference = (vehicle_heading - route_bearing + 180) % 360 - 180
        next_closest, next_closest_distance = nearby_pairs[1]

        if not (abs(difference) < 90) and next_closest_distance < 0.001:
            # bus seems to be heading the wrong way - does the bus go both ways on this road?
            # try the next closest pair of stops:
            route_bearing = calculate_bearing(
                next_closest[0].stop.latlong, next_closest[1].stop.latlong
            )

            difference = (vehicle_heading - route_bearing + 180) % 360 - 180
            if abs(difference) < 90:
                closest = next_closest
                distance = next_closest_distance

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

    return Progress(stop_times, closest[0], closest[1], progress, distance)


def add_progress_and_delay(item, stop_time=None):
    progress = get_progress(item, stop_time)
    if not progress:
        return

    item["progress"] = progress.to_json()
    when = parse_datetime(item["datetime"])
    when = timezone.localtime(when)
    when = timedelta(hours=when.hour, minutes=when.minute, seconds=when.second)

    prev_time = progress.prev_stop_time.departure_or_arrival()
    next_time = progress.next_stop_time.arrival_or_departure()

    # correct for timetable times being > 24 hours:
    if when - prev_time < -timedelta(hours=12):
        when += timedelta(hours=24)
    elif when - prev_time > timedelta(hours=12):
        when -= timedelta(hours=24)

    # TODO: cope with waittimes better

    expected_time = prev_time + (next_time - prev_time) * progress.progress
    delay = int((when - expected_time).total_seconds())
    item["delay"] = delay
