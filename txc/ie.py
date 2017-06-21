import os
import csv
import pygtfs
import datetime
from django.conf import settings
from .ni import Grouping, Timetable, Row


COLLECTIONS = (
    'luasbus', 'dublinbus', 'kenneallys', 'locallink', 'irishrail', 'ferries',
    'manda', 'finnegans', 'citylink', 'nitelink', 'buseireann', 'mcgeehan',
    'mkilbride', 'expressbus', 'edmoore', 'collins', 'luas', 'sro',
    'dublincoach', 'burkes', 'mhealy', 'kearns', 'josfoley', 'buggy',
    'jjkavanagh', 'citydirect', 'aircoach', 'matthews', 'wexfordbus',
    'dualway', 'tralee', 'sbloom', 'mcginley', 'swordsexpress', 'suirway',
    'sdoherty', 'pjmartley', 'mortons', 'mgray', 'mcgrath', 'mangan',
    'lallycoach', 'halpenny', 'eurobus', 'donnellys', 'cmadigan', 'bkavanagh',
    'ptkkenneally', 'farragher', 'fedateoranta'
)


def get_rows(csv_file):
    return csv.DictReader(line.decode('utf-8-sig') for line in csv_file)


def handle_trips(trips, day):
    i = 0
    head = None
    rows_map = {}

    for trip in sorted(trips, key=lambda t: t.stop_times[0].departure_time):
        previous = None
        visited_stops = set()

        for stop in sorted(trip.stop_times, key=lambda s: s.departure_time):
            stop_id = stop.stop_id
            if stop_id in rows_map:
                if stop_id in visited_stops:
                    if (
                        previous and previous.next and previous.next.atco_code == stop_id
                        and len(previous.next.times) == i
                    ):
                        row = previous.next
                    else:
                        row = Row(stop_id, ['     '] * i)
                        row.part.stop.name = stop.stop.stop_name
                        previous.append(row)
                else:
                    row = rows_map[stop_id]
            else:
                row = Row(stop_id, ['     '] * i)
                row.part.stop.name = stop.stop.stop_name
                rows_map[stop_id] = row
                if previous:
                    previous.append(row)
                else:
                    if head:
                        head.prepend(row)
                    head = row
            time = stop.departure_time or stop.arrival_time
            seconds = time.total_seconds()
            while seconds > 86400:
                seconds -= 86400
            time = datetime.time(int(seconds / 3600), int(seconds % 3600 / 60))
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


def get_timetable(service_code, day):
    parts = service_code.split('-', 1)
    path = parts[0]
    for collection in COLLECTIONS:
        if collection.startswith(path):
            path = collection
            break
    route_id = parts[1] + '-'

    path = os.path.join(settings.DATA_DIR, 'google_transit_' + collection + '.zip')

    schedule = pygtfs.Schedule('gtfs.zip')
    feed = None
    for possible_feed in schedule.feeds:
        if path.endswith(possible_feed.feed_name):
            feed = possible_feed
            break
    if not feed:
        pygtfs.overwrite_feed(schedule, path)  # this could take a while :(
    for possible_feed in schedule.feeds:
        if path.endswith(possible_feed.feed_name):
            feed = possible_feed
            break

    trips = {}
    routes = (route for route in feed.routes if route.id.startswith(route_id))
    for route in routes:
        for trip in route.trips:
            service = trip.service
            exception_type = None
            for exception in feed.service_exceptions:
                if exception.service_id == service.id and exception.date == day:
                    exception_type = exception.exception_type
                    break
            if exception_type == 2:  # service has been removed for the specified date
                continue
            elif exception_type is None:
                if day < service.start_date or day > service.end_date:
                    continue  # outside of dates
                if not getattr(service, day.strftime('%A').lower()):
                    continue
            if trip.direction_id in trips:
                trips[trip.direction_id].append(trip)
            else:
                trips[trip.direction_id] = [trip]

    t = Timetable()
    t.groupings = [handle_trips(trips[direction_id], day) for direction_id in trips]
    t.date = day
    for grouping in t.groupings:
        grouping.name = grouping.rows[0].part.stop.name + ' - ' + grouping.rows[-1].part.stop.name
    return [t]
