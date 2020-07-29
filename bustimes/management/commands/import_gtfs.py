import os
import time
import io
import csv
import logging
import zipfile
import requests
from datetime import datetime
from chardet.universaldetector import UniversalDetector
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.contrib.gis.geos import Point
from django.contrib.gis.geos import LineString, MultiLineString
from django.utils import timezone
from busstops.models import Region, DataSource, StopPoint, Service, StopUsage, Operator, AdminArea
from ...models import Route, Calendar, CalendarDate, Trip, StopTime
from ...timetables import get_stop_usages
from ...utils import download_if_changed


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


def read_file(archive, name):
    try:
        with archive.open(name) as open_file:
            detector = UniversalDetector()
            for line in open_file:
                detector.feed(line)
                if detector.done:
                    break
            detector.close()
            open_file.seek(0)
            for line in csv.DictReader(io.TextIOWrapper(open_file, encoding=detector.result['encoding'])):
                yield(line)
    except KeyError:
        # file doesn't exist
        return


def get_stop_id(stop_id):
    if '_merged_' in stop_id:
        parts = stop_id.split('_')
        return parts[parts.index('merged') - 1]
    return stop_id


def do_stops(archive):
    stops = {}
    admin_areas = {}
    stops_not_created = {}
    for line in read_file(archive, 'stops.txt'):
        stop_id = get_stop_id(line['stop_id'])
        if stop_id[0] in '78' and len(stop_id) <= 16:
            stops[stop_id] = StopPoint(
                atco_code=stop_id,
                latlong=Point(float(line['stop_lon']), float(line['stop_lat'])),
                common_name=line['stop_name'][:48],
                locality_centre=False,
                active=True
            )
        else:
            stops_not_created[stop_id] = line['stop_name'][:48]
    existing_stops = StopPoint.objects.in_bulk(stops)
    stops_to_create = [stop for stop in stops.values() if stop.atco_code not in existing_stops]

    for stop in stops_to_create:
        admin_area_id = stop.atco_code[:3]
        if admin_area_id not in admin_areas:
            admin_areas[admin_area_id] = AdminArea.objects.filter(id=admin_area_id).exists()
        if admin_areas[admin_area_id]:
            stop.admin_area_id = admin_area_id

    StopPoint.objects.bulk_create(stops_to_create)
    return StopPoint.objects.in_bulk(stops), stops_not_created


def handle_zipfile(path, collection, url):
    source = DataSource.objects.update_or_create(
        {
            'url': url,
            'datetime': timezone.now()
        }, name=f'{collection} GTFS'
    )[0]

    shapes = {}
    service_shapes = {}
    operators = {}
    routes = {}
    services = set()
    headsigns = {}

    with zipfile.ZipFile(path) as archive:

        for line in read_file(archive, 'shapes.txt'):
            shape_id = line['shape_id']
            if shape_id not in shapes:
                shapes[shape_id] = []
            shapes[shape_id].append(Point(float(line['shape_pt_lon']), float(line['shape_pt_lat'])))

        for line in read_file(archive, 'agency.txt'):
            operator, created = Operator.objects.get_or_create({
                'name': line['agency_name'],
                'region_id': 'LE'
            }, id=line['agency_id'], region__in=['CO', 'UL', 'MU', 'LE', 'NI'])
            if not created and operator.name != line['agency_name']:
                print(operator, line)
            operators[line['agency_id']] = operator

        for line in read_file(archive, 'routes.txt'):
            if line['route_short_name'] and len(line['route_short_name']) <= 8:
                route_id = line['route_short_name']
            elif line['route_long_name'] and len(line['route_long_name']) <= 4:
                route_id = line['route_long_name']
            else:
                route_id = line['route_id'].split()[0]

            service_code = collection + '-' + route_id
            assert len(service_code) <= 24

            defaults = {
                'region_id': 'LE',
                'line_name': line['route_short_name'],
                'description': line['route_long_name'],
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES.get(int(line['route_type']), ''),
                'current': True,
                'show_timetable': True
            }
            service, created = Service.objects.update_or_create(
                defaults,
                service_code=service_code,
                source=source
            )

            try:
                operator = operators[line['agency_id']]
                if service in services:
                    service.operator.add(operator)
                else:
                    service.operator.set([operator])
            except KeyError:
                pass
            services.add(service)

            route, created = Route.objects.update_or_create(
                {
                    'line_name': line['route_short_name'],
                    'description': line['route_long_name'],
                    'service': service,
                },
                source=source,
                code=line['route_id'],
            )
            if not created:
                route.trip_set.all().delete()
            routes[line['route_id']] = route

        stops, stops_not_created = do_stops(archive)

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
            route = routes[line['route_id']]
            trips[line['trip_id']] = Trip(
                route=route,
                calendar=calendars[line['service_id']],
                inbound=line['direction_id'] == '1'
            )
            if route.service_id not in service_shapes:
                service_shapes[route.service_id] = set()
            service_shapes[route.service_id].add(line['shape_id'])
            if line['trip_headsign']:
                if line['route_id'] not in headsigns:
                    headsigns[line['route_id']] = {
                        '0': set(),
                        '1': set(),
                    }
                headsigns[line['route_id']][line['direction_id']].add(line['trip_headsign'])
        for route_id in headsigns:
            route = routes[route_id]
            if not route.service.description:
                origins = headsigns[route_id]['1']
                destinations = headsigns[route_id]['0']
                origin = None
                destination = None
                if len(origins) <= 1 and len(destinations) <= 1:
                    if len(origins) == 1:
                        origin = list(origins)[0]
                    if len(destinations) == 1:
                        destination = list(destinations)[0]

                    if origin and ' - ' in origin:
                        route.service.inbound_description = origin
                        route.service.description = origin
                    if destination and ' - ' in destination:
                        route.service.outbound_description = destination
                        route.service.description = destination

                    if origin and destination and ' - ' not in origin:
                        route.service.description = route.service.outbound_description = f'{origin} - {destination}'
                        route.service.inbound_description = f'{destination} - {origin}'

                    route.service.save(update_fields=['description', 'inbound_description', 'outbound_description'])

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
            stop_time = StopTime(
                stop=stop,
                arrival=line['arrival_time'],
                departure=line['departure_time'],
                sequence=line['stop_sequence'],
            )
            if stop:
                trip.destination = stop
            elif line['stop_id'] in stops_not_created:
                stop_time.stop_code = stops_not_created[line['stop_id']]
            else:
                stop_time.stop_code = line['stop_id']
                print(line)
            stop_times.append(stop_time)
    trip.start = stop_times[0].departure
    trip.end = stop_times[-1].arrival
    trip.save()
    for stop_time in stop_times:
        stop_time.trip = trip
    StopTime.objects.bulk_create(stop_times)

    for service in services:
        if service.id in service_shapes:
            linestrings = [LineString(*shapes[shape]) for shape in service_shapes[service.id] if shape in shapes]
            service.geometry = MultiLineString(*linestrings)
            service.save(update_fields=['geometry'])

        groupings = get_stop_usages(Trip.objects.filter(route__service=service))

        service.stops.clear()
        stop_usages = [
            StopUsage(service=service, stop_id=stop_id, direction='outbound', order=i)
            for i, stop_id in enumerate(groupings[0]) if stop_id in stops
        ] + [
            StopUsage(service=service, stop_id=stop_id, direction='inbound', order=i)
            for i, stop_id in enumerate(groupings[1]) if stop_id in stops
        ]
        StopUsage.objects.bulk_create(stop_usages)

        service.region = Region.objects.filter(adminarea__stoppoint__service=service).annotate(
            Count('adminarea__stoppoint__service')
        ).order_by('-adminarea__stoppoint__service__count').first()
        if service.region:
            service.save(update_fields=['region'])

    for operator in operators.values():
        operator.region = Region.objects.filter(adminarea__stoppoint__service__operator=operator).annotate(
            Count('adminarea__stoppoint__service__operator')
        ).order_by('-adminarea__stoppoint__service__operator__count').first()
        if operator.region_id:
            operator.save(update_fields=['region'])

    print(source.service_set.filter(current=True).exclude(route__in=routes.values()).update(current=False))
    print(source.service_set.filter(current=True).exclude(route__trip__isnull=False).update(current=False))
    print(source.route_set.exclude(id__in=(route.id for route in routes.values())).delete())
    StopPoint.objects.filter(active=False, service__current=True).update(active=True)
    StopPoint.objects.filter(active=True, service__isnull=True).update(active=False)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help="Import data even if the GTFS feeds haven't changed")
        parser.add_argument('collections', nargs='*', type=str)

    def handle(self, *args, **options):
        for collection in options['collections'] or settings.IE_COLLECTIONS:
            path = os.path.join(settings.DATA_DIR, f'google_transit_{collection}.zip')
            url = f'https://www.transportforireland.ie/transitData/google_transit_{collection}.zip'
            modifed, _ = download_if_changed(path, url)
            if not modifed and not options['force']:
                continue
            print(collection)
            handle_zipfile(path, collection, url)
