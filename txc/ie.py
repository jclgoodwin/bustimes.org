import zipfile
import csv
#import calendar
from datetime import date
from .ni import Grouping, Timetable, Part, Stop, Row, contains, should_show


def get_rows(csv_file):
    return csv.DictReader(line.decode('utf-8-sig') for line in csv_file)


def handle_trips(trips):
    i = 0
    head = None
    rows_map = {}

    for trip in trips:
        previous = None
        visited_stops = set()

        for stop in trip:
            stop_id = stop['stop_id']
            if stop_id in rows_map:
                if stop_id in visited_stops:
                    if previous and previous.next and previous.next.stop_id == stop_id:
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
            time = stop['departure_time'] or stopusage['arrival_time']
            row.times.append(time)
            row.part.timingstatus = None # 'PTP' if stopusage['TimingPoint'] == 'T1' else 'OTH'
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
    print(head)
    while p:
        g.rows.append(p)
        p = p.next
    print(g.rows)
    t = Timetable()
    t.groupings = [g]
    t.date = date.today()
    return [t]

def get_data(path):
    with open(path) as open_file:
        data = json.load(open_file)
    return (data['Outbound'], data['Inbound'])


def get_timetable(service_code):
    parts = service_code.split('-', 1)
    archive_name = parts[0]
    route_id = parts[1] + '-'
    with zipfile.ZipFile('data/google_transit_' + archive_name + '.zip') as archive:
        print(archive.namelist())
        stops = {}
        with archive.open('stops.txt') as open_file:
            for row in get_rows(open_file):
                stops[row['stop_id']] = row
        with archive.open('routes.txt') as open_file:
            for row in get_rows(open_file):
                if row['route_id'].startswith(route_id):
                    print(row)
        trips = {}
        with archive.open('trips.txt') as open_file:
            for row in get_rows(open_file):
                if row['route_id'].startswith(route_id):
                    trips[row['trip_id']] = []
        with archive.open('stop_times.txt') as open_file:
            for row in get_rows(open_file):
                if row['trip_id'] in trips:
                    trips[row['trip_id']].append(row)
        return handle_trips(trips.values())
