from datetime import timedelta

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point, Polygon
from django.db.models import F, Q
from django.utils import timezone

from bustimes.models import RouteLink, StopTime, Trip
from bustimes.utils import get_calendars, get_routes


def get_trip(
    journey,
    datetime=None,
    date=None,
    destination_ref=None,
    departure_time=None,
    journey_ref=None,
):
    if not journey.service:
        return

    if journey_ref == journey.code:
        journey_ref = None

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
    elif len(journey.code) == 4 and journey.code.isdigit() and int(journey.code) < 2400:
        hours = int(journey.code[:-2])
        minutes = int(journey.code[-2:])
        start = timedelta(hours=hours, minutes=minutes)
    else:
        start = None

    if start is not None:
        start = Q(start=start)
        trips_at_start = trips.filter(start)

        if destination:
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
                if not journey_ref:
                    return
        except Trip.DoesNotExist:
            if destination and departure_time:
                try:
                    return trips.get(start, calendar__in=get_calendars(date))
                except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                    pass

    if not journey_ref:
        journey_ref = journey.code

    try:
        return trips.get(ticket_machine_code=journey_ref)
    except Trip.MultipleObjectsReturned:
        trips = trips.filter(calendar__in=get_calendars(date))
        return trips.filter(ticket_machine_code=journey_ref).first()
    except Trip.DoesNotExist:
        pass


def get_progress(journey, x, y):
    point = Point(x, y, srid=4326)

    route_link = (
        RouteLink.objects.filter(
            service=journey.service_id,
            geometry__bboverlaps=point.buffer(0.001),
            from_stop__stoptime__trip=journey.trip_id,
            to_stop__stoptime__trip=journey.trip_id,
            to_stop__stoptime__id__gt=F("from_stop__stoptime__id"),
        )
        .annotate(
            distance=Distance("geometry", point),
            from_stoptime=F("from_stop__stoptime"),
            to_stoptime=F("to_stop__stoptime"),
        )
        .order_by("distance")
        .first()
    )

    if route_link:
        return StopTime.objects.filter(
            id__in=(route_link.from_stoptime, route_link.to_stoptime)
        )

    boxes = []
    previous = None
    for stop_time in StopTime.objects.filter(trip=journey.trip_id).select_related(
        "stop"
    ):
        if stop_time.stop and stop_time.stop.latlong:
            if previous:
                xs = (previous.stop.latlong.x, stop_time.stop.latlong.x)
                ys = (previous.stop.latlong.y, stop_time.stop.latlong.y)
                box = Polygon.from_bbox((min(xs), min(ys), max(xs), max(ys)))
                if not box.distance(point):
                    return previous, stop_time
                boxes.append(box)
            previous = stop_time
