import os
import io
import csv
import logging
import zipfile
from requests_html import HTMLSession
from datetime import datetime
from django.utils.dateparse import parse_duration
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Exists, OuterRef
from django.contrib.gis.geos import GEOSGeometry, LineString, MultiLineString
from busstops.models import Region, DataSource, StopPoint, Service, Operator, AdminArea
from ...models import Route, Calendar, CalendarDate, Trip, StopTime
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
            with io.TextIOWrapper(open_file, encoding="utf-8-sig") as wrapped_file:
                yield from csv.DictReader(wrapped_file)
    except KeyError:
        # file doesn't exist
        return


def get_stop_id(stop_id):
    if '_merged_' in stop_id:
        parts = stop_id.split('_')
        return parts[parts.index('merged') - 1]
    return stop_id


def get_calendar(line):
    return Calendar(
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
            logger.info(f"{operator} {line}")
        return operator

    def do_stops(self, archive):
        stops = {}
        admin_areas = {}
        stops_not_created = {}
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
        existing_stops = StopPoint.objects.only('atco_code').in_bulk(stops)
        stops_to_create = [stop for stop in stops.values() if stop.atco_code not in existing_stops]

        for stop in stops_to_create:
            admin_area_id = stop.atco_code[:3]
            if admin_area_id not in admin_areas:
                admin_areas[admin_area_id] = AdminArea.objects.filter(id=admin_area_id).exists()
            if admin_areas[admin_area_id]:
                stop.admin_area_id = admin_area_id

        StopPoint.objects.bulk_create(stops_to_create, batch_size=1000)
        return StopPoint.objects.only('atco_code').in_bulk(stops), stops_not_created

    def handle_route(self, line):

        line_name = line['route_short_name']
        description = line['route_long_name']
        if not line_name and ' ' not in description:
            line_name = description
        if line_name.endswith('x'):  # Aircoach
            line_name = line_name.replace('-', '').upper()

        service = self.source.service_set.filter(
            Q(line_name__iexact=line_name) |
            Exists(
                Route.objects.filter(code=line['route_id'], service=OuterRef('id'))
            ) | Q(service_code=line['route_id'])
        ).order_by('id').first()
        if not service:
            service = Service(source=self.source)

        service.service_code = line['route_id']
        service.line_name = line_name
        service.description = description
        service.date = self.source.datetime.date()
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

            for line in read_file(archive, 'routes.txt'):
                self.handle_route(line)

            stops, stops_not_created = self.do_stops(archive)

            calendars = {}
            for line in read_file(archive, 'calendar.txt'):
                calendar = get_calendar(line)
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
                    inbound=line['direction_id'] == '1',
                    ticket_machine_code=line['trip_id']
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

            trip = None
            previous_line = None

            for line in read_file(archive, 'stop_times.txt'):

                if not previous_line or previous_line['trip_id'] != line['trip_id']:

                    if trip:
                        trip.destination = stops.get(previous_line['stop_id'])
                        trip.end = parse_duration(previous_line['arrival_time'])

                    trip = trips[line['trip_id']]
                    trip.start = parse_duration(line['departure_time'])

                previous_line = line

            # last trip:
            trip.destination = stops.get(line['stop_id'])
            trip.end = parse_duration(line['arrival_time'])

            Trip.objects.bulk_create(trips.values(), batch_size=1000)

            i = 0
            stop_times = []

            for line in read_file(archive, 'stop_times.txt'):
                stop = stops.get(line['stop_id'])

                stop_time = StopTime(
                    arrival=parse_duration(line['arrival_time']),
                    departure=parse_duration(line['departure_time']),
                    sequence=line['stop_sequence'],
                    trip=trips[line['trip_id']]
                )
                if line.get('pickup_type') == '1':  # "No pickup available"
                    stop_time.pick_up = False

                if stop:
                    stop_time.stop = stop
                elif line['stop_id'] in stops_not_created:
                    stop_time.stop_code = stops_not_created[line['stop_id']]['stop_name']
                else:
                    stop_time.stop_code = line['stop_id']
                    print(line)

                if stop_time.arrival == stop_time.departure:
                    stop_time.arrival = None

                stop_times.append(stop_time)

                if i == 999:
                    StopTime.objects.bulk_create(stop_times)
                    stop_times = []
                    i = 0
                else:
                    i += 1

                previous_line = line

        # last trip
        if not stop_time.arrival:
            stop_time.arrival = stop_time.departure
            stop_time.departure = None

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
        logger.info(current_services.exclude(route__in=self.routes.values()).update(current=False))
        logger.info(current_services.exclude(route__trip__isnull=False).update(current=False))
        logger.info(self.source.route_set.exclude(id__in=(route.id for route in self.routes.values())).delete())
        StopPoint.objects.filter(active=False, service__current=True).update(active=True)
        StopPoint.objects.filter(active=True, service__isnull=True).update(active=False)

    def handle(self, *args, **options):
        prefix = "https://www.transportforireland.ie"

        if options['collections']:
            collections = [f'google_transit_{collection}.zip' for collection in options['collections']]
        else:
            session = HTMLSession()

            response = session.get(f'{prefix}/transitData/PT_Data.html')
            collections = response.html.find('a[href^="google_transit_"]')

            collections = options['collections'] or set(element.attrs['href'] for element in collections)

        for collection in collections:
            path = os.path.join(settings.DATA_DIR, collection)
            url = f'{prefix}/transitData/{collection}'
            modifed, last_modified = download_if_changed(path, url)
            if modifed or options['force']:

                collection = collection.removeprefix('google_transit_').removesuffix('.zip')

                self.source, _ = DataSource.objects.get_or_create(
                    {'url': url},
                    name=f'{collection} GTFS'
                )
                if options['force'] or self.source.older_than(last_modified):
                    logger.info(f"{collection} {last_modified}")
                    if last_modified:
                        self.source.datetime = last_modified
                    self.handle_zipfile(path)
