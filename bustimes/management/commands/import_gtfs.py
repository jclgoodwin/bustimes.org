import os
import time
import io
import csv
import logging
import zipfile
import requests
from datetime import datetime
from chardet.universaldetector import UniversalDetector
from email.utils import parsedate
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.contrib.gis.geos import Point
# from django.contrib.gis.geos import LineString, MultiLineString
from django.utils import timezone
from busstops.models import Region, DataSource, StopPoint, Service, StopUsage, Operator
from ...models import Route, Calendar, CalendarDate, Trip, StopTime
from ...timetables import get_stop_usages


logger = logging.getLogger(__name__)

MODES = {
    0: 'tram',
    2: 'rail',
    3: 'bus',
    4: 'ferry',
    200: 'coach',
}
SESSION = requests.Session()


def parse_date(string):
    return datetime.strptime(string, '%Y%m%d')


def write_zip_file(path, response):
    with open(path, 'wb') as zip_file:
        for chunk in response.iter_content(chunk_size=102400):
            zip_file.write(chunk)


def download_if_modified(path, url):
    if os.path.exists(path):
        last_modified = time.localtime(os.path.getmtime(path))
        headers = {
            'if-modified-since': time.asctime(last_modified)
        }
        response = SESSION.head(url, headers=headers, timeout=5, allow_redirects=True)
        if not response.ok:
            response = SESSION.get(url, headers=headers, timeout=5, stream=True)
        if response.status_code == 304:
            return False  # not modified
        if 'last-modified' in response.headers and parsedate(response.headers['last-modified']) <= last_modified:
            return False
    response = SESSION.get(url, stream=True)
    write_zip_file(path, response)
    return True


def read_file(archive, name):
    try:
        with archive.open(name) as open_file:
            detector = UniversalDetector()
            for line in open_file:
                detector.feed(line)
                if detector.done:
                    break
            detector.close()
    except KeyError:
        return
    with archive.open(name) as open_file:
        for line in csv.DictReader(io.TextIOWrapper(open_file, encoding=detector.result['encoding'])):
            yield(line)


def get_stop_id(stop_id):
    if '_merged_' in stop_id:
        parts = stop_id.split('_')
        return parts[parts.index('merged') - 1]
    return stop_id


def do_stops(archive):
    stops = {}
    for line in read_file(archive, 'stops.txt'):
        stop_id = get_stop_id(line['stop_id'])
        if stop_id[0] in '78' and len(stop_id) <= 16:
            stops[stop_id] = StopPoint(
                atco_code=stop_id,
                latlong=Point(float(line['stop_lon']), float(line['stop_lat'])),
                common_name=line['stop_name'][:48],
                locality_centre=False,
                admin_area_id=stop_id[:3],
                active=True
            )
        else:
            print(stop_id)
    existing_stops = StopPoint.objects.in_bulk(stops)
    StopPoint.objects.bulk_create(stop for stop in stops.values() if stop.atco_code not in existing_stops)
    return StopPoint.objects.in_bulk(stops)


def handle_zipfile(path, collection):
    source = DataSource.objects.update_or_create({'datetime': timezone.now()}, name=f'{collection} GTFS')[0]

    with zipfile.ZipFile(path) as archive:

        shapes = {}
        for line in read_file(archive, 'shapes.txt'):
            shape_id = line['shape_id']
            if shape_id not in shapes:
                shapes[shape_id] = []
            shapes[shape_id].append(Point(float(line['shape_pt_lon']), float(line['shape_pt_lat'])))

        operators = {}
        for line in read_file(archive, 'agency.txt'):
            operator, created = Operator.objects.get_or_create({
                'name': line['agency_name'],
                'region_id': 'LE'
            }, id=line['agency_id'], region__in=['CO', 'UL', 'MU', 'LE', 'NI'])
            if not created and operator.name != line['agency_name']:
                print(operator, line)
            operators[line['agency_id']] = operator

        routes = {}
        for line in read_file(archive, 'routes.txt'):
            if line['route_short_name'] and len(line['route_short_name']) <= 8:
                route_id = line['route_short_name']
            elif line['route_long_name'] and len(line['route_long_name']) <= 4:
                route_id = line['route_long_name']
            else:
                route_id = line['route_id'].split()[0]

            if collection == 'eurobus':
                service_code = 'dublincoach' + '-' + route_id
            else:
                service_code = collection + '-' + route_id
            assert len(service_code) <= 24

            defaults = {
                'region_id': 'LE',
                'line_name': line['route_short_name'],
                'description': line['route_long_name'],
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES.get(line['route_type'], ''),
                'current': True,
                'show_timetable': True
            }
            service, created = Service.objects.update_or_create(
                defaults,
                service_code=service_code,
                source=source
            )

            route, created = Route.objects.update_or_create(
                source=source,
                code=line['route_id'],
                service=service,
            )
            if not created:
                route.trip_set.all().delete()
            routes[line['route_id']] = route

        stops = do_stops(archive)

        calendars = {}
        for line in read_file(archive, 'calendar.txt'):
            calendar = Calendar(
                mon='1' == line['monday'],
                tue='1' == line['tuesday'],
                wed='1' == line['wednesday'],
                thu='1' == line['thursday'],
                fri='1' == line['friday'],
                sat='1' == line['saturday'],
                sun='1' == line['sunday'],
                start_date=parse_date(line['start_date']),
                end_date=parse_date(line['end_date']),
            )
            calendar.save()
            calendars[line['service_id']] = calendar

        for line in read_file(archive, 'calendar_dates.txt'):
            CalendarDate.objects.create(
                calendar=calendars[line['service_id']],
                start_date=parse_date(line['date']),
                end_date=parse_date(line['date']),
                operation=line['exception_type'] == '1'
            )

        trips = {}
        for line in read_file(archive, 'trips.txt'):
            trips[line['trip_id']] = Trip(
                route=routes[line['route_id']],
                calendar=calendars[line['service_id']],
                inbound=line['direction_id'] == '1'
            )

        stop_times = []
        trip_id = None
        trip = None
        for line in read_file(archive, 'stop_times.txt'):
            if trip_id != line['trip_id']:
                if trip:
                    trip.start = stop_times[0].departure
                    trip.end = stop_times[-1].arrival
                    trip.save()
                    for stop_time in stop_times:
                        stop_time.trip = trip
                    StopTime.objects.bulk_create(stop_times)
                    stop_times = []
                trip = Trip()
            trip_id = line['trip_id']
            trip = trips[trip_id]
            stop = stops.get(line['stop_id'])
            if stop:
                trip.destination = stop
            stop_times.append(
                StopTime(
                    stop_code=line['stop_id'],
                    stop=stop,
                    arrival=line['arrival_time'],
                    departure=line['departure_time'],
                    sequence=line['stop_sequence'],
                )
            )
        trip.start = stop_times[0].departure
        trip.end = stop_times[-1].arrival
        trip.save()
        for stop_time in stop_times:
            stop_time.trip = trip
        StopTime.objects.bulk_create(stop_times)

        for route in routes.values():
            groupings = get_stop_usages(route.trip_set.all())

            route.service.stops.clear()
            stop_usages = [
                StopUsage(service=route.service, stop_id=stop_id, direction='outbound', order=i)
                for i, stop_id in enumerate(groupings[0]) if stop_id[0] in '78'
            ] + [
                StopUsage(service=route.service, stop_id=stop_id, direction='inbound', order=i)
                for i, stop_id in enumerate(groupings[1]) if stop_id[0] in '78'
            ]
            StopUsage.objects.bulk_create(stop_usages)

        for service in Service.objects.all():
            service.region = Region.objects.filter(adminarea__stoppoint__service=service).annotate(
                Count('adminarea__stoppoint__service')
            ).order_by('-adminarea__stoppoint__service__count').first()
            if service.region:
                service.save()

        for operator in Operator.objects.all():
            operator.region = Region.objects.filter(adminarea__stoppoint__service__operator=operator).annotate(
                Count('adminarea__stoppoint__service__operator')
            ).order_by('-adminarea__stoppoint__service__operator__count').first()
            if operator.region_id:
                operator.save()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help="Import data even if the GTFS feeds haven't changed")

    def handle(self, *args, **options):
        for collection in settings.IE_COLLECTIONS:
            path = os.path.join(settings.DATA_DIR, f'google_transit_{collection}.zip')
            url = f'https://www.transportforireland.ie/transitData/google_transit_{collection}.zip'
            downloaded = download_if_modified(path, url)
            if not downloaded and not options['force']:
                continue
            print(collection)
            handle_zipfile(path, collection)
