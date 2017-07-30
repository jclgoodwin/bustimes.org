import datetime
from django.db.models import Min
from django.conf import settings
from multigtfs.models import Feed, Trip
from .ni import Grouping, Timetable, Row


def handle_trips(trips, day):
    i = 0
    head = None
    rows_map = {}

    if not day:
        day = datetime.date.today()
    midnight = datetime.datetime.combine(day, datetime.time())

    for trip in trips:
        previous = None
        visited_stops = set()

        for stop in trip.stoptime_set.order_by('departure_time').select_related('stop'):
            stop_id = stop.stop.stop_id
            if stop_id in rows_map:
                if stop_id in visited_stops:
                    if (
                        previous and previous.next and previous.next.atco_code == stop_id
                        and len(previous.next.times) == i
                    ):
                        row = previous.next
                    else:
                        row = Row(stop_id, ['     '] * i)
                        row.part.stop.name = stop.stop.name
                        previous.append(row)
                else:
                    row = rows_map[stop_id]
            else:
                row = Row(stop_id, ['     '] * i)
                row.part.stop.name = stop.stop.name
                rows_map[stop_id] = row
                if previous:
                    previous.append(row)
                else:
                    if head:
                        head.prepend(row)
                    head = row
            time = datetime.timedelta(seconds=(stop.departure_time or stop.arrival_time).seconds)
            time = (midnight + time).time()
            row.times.append(time)
            row.part.timingstatus = None
            previous = row
            visited_stops.add(stop_id)

        if i:
            p = head
            while p:
                if len(p.times) == i:
                    p.times.append('     ')
                p = p.next
        i += 1
    p = head
    g = Grouping()

    while p:
        g.rows.append(p)
        p = p.next
    return g


def get_timetable(routes, day):
    if not routes:
        return

    trips_dict = {}

    trips = Trip.objects.filter(route__in=routes)
    trips = trips.annotate(departure_time=Min('stoptime__departure_time')).order_by('departure_time')
    for trip in trips.select_related('service'):
        if day:
            service = trip.service
            exception = service.servicedate_set.filter(date=day).first()
            if exception and exception.exception_type == 2:  # service has been removed for the specified date
                continue
            if exception is None:
                if day < service.start_date or day > service.end_date:  # outside of dates
                    continue
                if not getattr(service, day.strftime('%A').lower()):  # day of week
                    continue
        if trip.direction in trips_dict:
            trips_dict[trip.direction].append(trip)
        else:
            trips_dict[trip.direction] = [trip]

    t = Timetable()
    t.groupings = [handle_trips(trips_dict[direction], day) for direction in trips_dict]
    t.date = day
    for grouping in t.groupings:
        grouping.name = grouping.rows[0].part.stop.name + ' - ' + grouping.rows[-1].part.stop.name
    return t


def get_timetables(service_code, day):
    parts = service_code.split('-', 1)
    path = parts[0]
    for collection in settings.IE_COLLECTIONS:
        if collection.startswith(path):
            path = collection
            break
    route_id = parts[1] + '-'
    try:
        feed = Feed.objects.filter(name=collection).latest('created')
    except Feed.DoesNotExist:
        return
    timetable = get_timetable(feed.route_set.filter(route_id__startswith=route_id), day)
    if timetable:
        return [timetable]
