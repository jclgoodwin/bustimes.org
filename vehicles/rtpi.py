from datetime import timedelta
from itertools import pairwise

import shapely
from django.db.models import Q
from django.utils import timezone
from sql_util.utils import Exists

from bustimes.models import StopTime, Trip
from bustimes.utils import get_calendars, get_routes


def get_trip(
    journey,
    datetime=None,
    date=None,
    operator_ref=None,
    origin_ref=None,
    destination_ref=None,
    departure_time=None,
    journey_code="",
):
    if not journey.service:
        return

    if not datetime:
        datetime = journey.datetime
    if not date:
        date = (departure_time or datetime).date()

    routes = get_routes(journey.service.route_set.select_related("source"), date)
    if not routes:
        return
    trips = Trip.objects.filter(route__in=routes)

    if destination_ref and " " not in destination_ref and destination_ref[:3].isdigit():
        destination = Q(destination=destination_ref)
    else:
        destination = None

    if journey.direction == "outbound":
        direction = Q(inbound=False)
    elif journey.direction == "inbound":
        direction = Q(inbound=True)
    else:
        direction = None

    if departure_time:
        start = timezone.localtime(departure_time)
        start = timedelta(hours=start.hour, minutes=start.minute)
    elif len(journey_code) == 4 and journey_code.isdigit() and int(journey_code) < 2400:
        hours = int(journey_code[:-2])
        minutes = int(journey_code[-2:])
        start = timedelta(hours=hours, minutes=minutes)
    else:
        start = None

    if start is not None:
        trips_at_start = trips.filter(start=start)

        # special strategy for TfL data
        if operator_ref == "TFLO" and departure_time and origin_ref and destination_ref:
            trips_at_start = trips_at_start.filter(
                Exists("stoptime", filter=Q(stop=origin_ref)),
                Exists("stoptime", filter=Q(stop=destination_ref)),
            )
        elif destination:
            if direction:
                destination |= direction
            trips_at_start = trips_at_start.filter(destination)
        elif direction:
            trips_at_start = trips_at_start.filter(direction)

        try:
            return trips_at_start.get()
        except Trip.MultipleObjectsReturned:
            try:
                return trips_at_start.get(calendar__in=get_calendars(date))
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass
        except Trip.DoesNotExist:
            if destination and departure_time:
                try:
                    return trips.get(start=start, calendar__in=get_calendars(date))
                except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                    pass

    if not journey.code:
        return

    trips = trips.filter(
        Q(ticket_machine_code=journey.code) | Q(vehicle_journey_code=journey.code)
    )

    try:
        return trips.get()
    except Trip.DoesNotExist:
        return
    except Trip.MultipleObjectsReturned:
        return trips.filter(calendar__in=get_calendars(date)).first()


def get_progress(journey, x, y):
    point = shapely.Point(x, y)

    stop_times = list(
        StopTime.objects.filter(trip=journey.trip_id)
        .filter(stop__latlong__isnull=False)
        .select_related("stop")
    )

    minimum_distance = None
    closest_pair = None
    # closest_linestring = None

    for a, b in pairwise(stop_times):
        line_string = shapely.LineString([a.stop.latlong, b.stop.latlong])
        distance = line_string.distance(point)

        if minimum_distance is None or distance < minimum_distance:
            minimum_distance = distance
            closest_pair = a, b
            # closest_linestring = line_string

    if closest_pair is not None:
        return closest_pair
