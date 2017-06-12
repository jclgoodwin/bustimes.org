import os
import zipfile
import csv
from datetime import datetime
from django.conf import settings
from .ni import Grouping, Timetable, Row


def get_rows(csv_file):
    return csv.DictReader(line.decode('utf-8-sig') for line in csv_file)


def handle_trips(trips, day):
    i = 0
    head = None
    rows_map = {}

    for trip in sorted(trips, key=lambda t: t['stops'][0]['departure_time']):
        previous = None
        visited_stops = set()

        for stop in trip['stops']:
            stop_id = stop['stop_id']
            if stop_id in rows_map:
                if stop_id in visited_stops:
                    if previous and previous.next and previous.next.atco_code == stop_id and len(previous.next.times) == i:
                        row = previous.next
                    else:
                        row = Row(stop_id, ['     '] * i)
                        previous.append(row)
                else:
                    row = rows_map[stop_id]
            else:
                row = Row(stop_id, ['     '] * i)
                rows_map[stop_id] = row
                if previous:
                    previous.append(row)
                else:
                    if head:
                        head.prepend(row)
                    head = row
            time = stop['departure_time'] or stop['arrival_time']
            if int(time[:2]) > 23:
                time = str(int(time[:2]) - 24) + time[2:]
            time = datetime.strptime(time, '%H:%M:%S').time()
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
    if path == 'dublincoac':
        path += 'h'
    route_id = parts[1] + '-'
    path = os.path.join(settings.DATA_DIR, 'google_transit_' + path + '.zip')

    with zipfile.ZipFile(path) as archive:
        stops = {}
        with archive.open('stops.txt') as open_file:
            for row in get_rows(open_file):
                stops[row['stop_id']] = row

        routes = {}
        with archive.open('routes.txt') as open_file:
            for row in get_rows(open_file):
                if row['route_id'].startswith(route_id):
                    routes[row['route_id']] = row

        calendar = {}
        with archive.open('calendar.txt') as open_file:
            for row in get_rows(open_file):
                row['exceptions'] = []
                calendar[row['service_id']] = row
        with archive.open('calendar_dates.txt') as open_file:
            for row in get_rows(open_file):
                calendar[row['service_id']]['exceptions'].append(row)

        trips = {}
        with archive.open('trips.txt') as open_file:
            for row in get_rows(open_file):
                service = calendar[row['service_id']]
                exception_type = None
                for exception in service['exceptions']:
                    if datetime.strptime(exception['date'], '%Y%m%d').date() == day:
                        exception_type = exception['exception_type']
                        break
                if exception_type == '2':  # service has been removed for the specified date
                    continue
                elif exception_type is None:
                    if (
                            day < datetime.strptime(service['start_date'], '%Y%m%d').date() or
                            day > datetime.strptime(service['end_date'], '%Y%m%d').date()
                    ):
                        continue  # outside of dates
                    if service[day.strftime('%A').lower()] == '0':
                        continue
                if row['direction_id'] not in trips:
                    trips[row['direction_id']] = {}
                if row['route_id'].startswith(route_id):
                    row['stops'] = []
                    trips[row['direction_id']][row['trip_id']] = row
        with archive.open('stop_times.txt') as open_file:
            for row in get_rows(open_file):
                for dir in trips:
                    if row['trip_id'] in trips[dir]:
                        trips[dir][row['trip_id']]['stops'].append(row)
                        break

        t = Timetable()
        t.groupings = [handle_trips(trips[dir].values(), day) for dir in trips]
        t.date = day
        for grouping in t.groupings:
            for row in grouping.rows:
                row.part.stop.name = stops[row.part.stop.atco_code]['stop_name']
                if not grouping.name:
                    grouping.name = row.part.stop.name
            if grouping.name:
                grouping.name += ' - ' + row.part.stop.name
        return [t]
