import os
import io
import csv
import logging
import zipfile
from requests_html import HTMLSession
from datetime import datetime, timedelta
from chardet.universaldetector import UniversalDetector
from django.utils.dateparse import parse_duration
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.contrib.gis.geos import GEOSGeometry, LineString, MultiLineString
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
            with io.TextIOWrapper(open_file, encoding=detector.result['encoding']) as wrapped_file:
                for line in csv.DictReader(wrapped_file):
                    yield line
    except KeyError:
        # file doesn't exist
        return


def get_stop_id(stop_id):
    if '_merged_' in stop_id:
        parts = stop_id.split('_')
        return parts[parts.index('merged') - 1]
    return stop_id


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help="Import data even if the GTFS feeds haven't changed")
        parser.add_argument('collections', nargs='*', type=str)

    def handle_operator(self, line):
        operator, created = Operator.objects.get_or_create({
            'name': line['agency_name'],
            'region_id': 'LE'
        }, id=line['agency_id'], region__in=['CO', 'UL', 'MU', 'LE', 'NI'])
        if operator.name != line['agency_name']:
            print(operator, line)
        return operator

    def do_stops(self, archive):
        stops = {}
        admin_areas = {}
        stops_not_created = {}
        self.stop_timezones = {}
        for line in read_file(archive, 'stops.txt'):
            stop_id = get_stop_id(line['stop_id'])
            if stop_id[0] in '78' and len(stop_id) <= 16:
                stops[stop_id] = StopPoint(
                    atco_code=stop_id,
                    latlong=GEOSGeometry(f"POINT({line['stop_lon']} {line['stop_lat']})"),
                    common_name=line['stop_name'][:48],
                    locality_centre=False,
                    active=True
                )
            else:
                stops_not_created[stop_id] = line
            if 'stop_timezone' in line:
                self.stop_timezones[stop_id] = line['stop_timezone']
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

    def handle_route(self, line):
        try:
            service = Service.objects.filter(
                Q(route__code=line['route_id']) | Q(service_code=line['route_id']),
                source=self.source
            ).get()
        except Service.DoesNotExist:
            service = Service(source=self.source)

        service.service_code = line['route_id']
        service.line_name = line['route_short_name']
        service.description = line['route_long_name']
        if not service.line_name and ' ' not in service.description:
            service.line_name = service.description
        if service.line_name.endswith('x'):  # Aircoach
            service.line_name = service.line_name.replace('-', '').upper()
        service.date = self.source.datetime.strftime('%Y-%m-%d')
        service.mode = MODES.get(int(line['route_type']), '')
        service.current = True
        service.service_code = line['route_id']
        service.save()

        try:
            operator = self.operators[line['agency_id']]
            if service.id in self.services:
                service.operator.add(operator)
            else:
                service.operator.set([operator])
        except KeyError:
            pass
        self.services[service.id] = service

        route, created = Route.objects.update_or_create(
            {
                'line_name': service.line_name,
                'description': service.description,
                'service': service,
            },
            source=self.source,
            code=line['route_id'],
        )
        if not created:
            route.trip_set.all().delete()
        self.routes[line['route_id']] = route

    def handle_zipfile(self, path):
        self.shapes = {}
        self.service_shapes = {}
        self.operators = {}
        self.routes = {}
        self.services = {}
        self.agency_timezones = {}
        headsigns = {}

        with zipfile.ZipFile(path) as archive:

            for line in read_file(archive, 'shapes.txt'):
                shape_id = line['shape_id']
                if shape_id not in self.shapes:
                    self.shapes[shape_id] = []
                self.shapes[shape_id].append(
                    GEOSGeometry(f"POINT({line['shape_pt_lon']} {line['shape_pt_lat']})")
                )

            for line in read_file(archive, 'agency.txt'):
                self.operators[line['agency_id']] = self.handle_operator(line)
                self.agency_timezones['agency_id'] = line['agency_timezone']

            for line in read_file(archive, 'routes.txt'):
                self.handle_route(line)

            stops, stops_not_created = self.do_stops(archive)

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
                route = self.routes.get(line['route_id'])
                if not route:
                    continue
                trips[line['trip_id']] = Trip(
                    route=route,
                    calendar=calendars[line['service_id']],
                    inbound=line['direction_id'] == '1'
                )
                if line['shape_id']:
                    if route.service_id not in self.service_shapes:
                        self.service_shapes[route.service_id] = set()
                    self.service_shapes[route.service_id].add(line['shape_id'])
                if line['trip_headsign']:
                    if line['route_id'] not in headsigns:
                        headsigns[line['route_id']] = {
                            '0': set(),
                            '1': set(),
                        }
                    headsigns[line['route_id']][line['direction_id']].add(line['trip_headsign'])
            for route_id in headsigns:
                route = self.routes[route_id]
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

            utc = all(timezone == 'UTC' for timezone in self.agency_timezones.values())

            stop_times = []
            trip_id = None
            trip = None
            stop_time = None
            for line in read_file(archive, 'stop_times.txt'):
                if line['trip_id'] not in trips:
                    continue
                if trip_id != line['trip_id']:
                    # previous trip
                    if trip:
                        if not stop_time.arrival:
                            stop_time.arrival = stop_time.departure
                            stop_time.departure = None
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
                arrival_time = parse_duration(line['arrival_time'])
                departure_time = parse_duration(line['departure_time'])
                if utc and self.stop_timezones and self.stop_timezones[line['stop_id']] == 'Europe/London':
                    # TODO: fix assumption of British Summer Time
                    arrival_time += timedelta(hours=1)
                    departure_time += timedelta(hours=1)

                if arrival_time == departure_time:
                    arrival_time = None
                stop_time = StopTime(
                    stop=stop,
                    arrival=arrival_time,
                    departure=departure_time,
                    sequence=line['stop_sequence'],
                )
                if line.get('pickup_type') == '1':  # "No pickup available"
                    stop_time.pick_up = False

                if stop:
                    trip.destination = stop
                elif line['stop_id'] in stops_not_created:
                    stop_time.stop_code = stops_not_created[line['stop_id']]['stop_name']
                else:
                    stop_time.stop_code = line['stop_id']
                    print(line)
                stop_times.append(stop_time)

        # last trip
        if not stop_time.arrival:
            stop_time.arrival = stop_time.departure
            stop_time.departure = None
        trip.start = stop_times[0].departure
        trip.end = stop_times[-1].arrival
        trip.save()
        for stop_time in stop_times:
            stop_time.trip = trip
        StopTime.objects.bulk_create(stop_times)

        for service in self.services.values():
            if service.id in self.service_shapes:
                linestrings = [LineString(*self.shapes[shape])
                               for shape in self.service_shapes[service.id]
                               if shape in self.shapes]
                service.geometry = MultiLineString(*linestrings)
                service.save(update_fields=['geometry'])
            else:
                pass

            service.do_stop_usages()

            service.region = Region.objects.filter(adminarea__stoppoint__service=service).annotate(
                Count('adminarea__stoppoint__service')
            ).order_by('-adminarea__stoppoint__service__count').first()
            if service.region:
                service.save(update_fields=['region'])
            service.update_search_vector()

        self.source.save(update_fields=['datetime'])

        for operator in self.operators.values():
            operator.region = Region.objects.filter(adminarea__stoppoint__service__operator=operator).annotate(
                Count('adminarea__stoppoint__service__operator')
            ).order_by('-adminarea__stoppoint__service__operator__count').first()
            if operator.region_id:
                operator.save(update_fields=['region'])

        current_services = self.source.service_set.filter(current=True)
        print(current_services.exclude(route__in=self.routes.values()).update(current=False))
        print(current_services.exclude(route__trip__isnull=False).update(current=False))
        print(self.source.route_set.exclude(id__in=(route.id for route in self.routes.values())).delete())
        StopPoint.objects.filter(active=False, service__current=True).update(active=True)
        StopPoint.objects.filter(active=True, service__isnull=True).update(active=False)

    def handle(self, *args, **options):
        if options['collections']:
            collections = [f'google_transit_{collection}.zip' for collection in options['collections']]
        else:
            session = HTMLSession()

            response = session.get('https://www.transportforireland.ie/transitData/PT_Data.html')
            collections = response.html.find('a[href^="google_transit_"]')

            collections = options['collections'] or set(element.attrs['href'] for element in collections)

        for collection in collections:
            path = os.path.join(settings.DATA_DIR, collection)
            url = f'https://www.transportforireland.ie/transitData/{collection}'
            modifed, last_modified = download_if_changed(path, url)
            if modifed or options['force']:

                collection = collection.removeprefix('google_transit_').removesuffix('.zip')

                self.source, _ = DataSource.objects.get_or_create(
                    {'url': url},
                    name=f'{collection} GTFS'
                )
                if options['force'] or self.source.older_than(last_modified):
                    print(collection, last_modified)
                    self.source.datetime = last_modified
                    self.handle_zipfile(path)
