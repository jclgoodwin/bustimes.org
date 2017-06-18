import os
import time
import zipfile
import csv
import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from txc.ie import COLLECTIONS
from ...models import Operator, Service, StopPoint, StopUsage, Region


MODES = {
    '2': 'rail',
    '3': 'bus',
    '4': 'ferry'
}


def get_rows(csv_file):
    return csv.DictReader(line.decode('utf-8-sig') for line in csv_file)


def write_zip_file(path, response):
    with open(path, 'wb') as zip_file:
        for chunk in response.iter_content(chunk_size=102400):
            zip_file.write(chunk)


class Command(BaseCommand):
    @transaction.atomic
    def handle_zipfile(self, archive_name, collection):
        collection = collection[:10]
        Service.objects.filter(service_code__startswith=collection).update(current=False)

        routes = {}
        trips = {}
        agencies = {}
        operators = set()
        with zipfile.ZipFile(archive_name) as archive:
            with archive.open('stops.txt') as csv_file:
                for row in get_rows(csv_file):
                    if row['stop_id'][0] in '78' and not StopPoint.objects.filter(atco_code=row['stop_id']).exists():
                        StopPoint.objects.create(
                            atco_code=row['stop_id'],
                            latlong=Point(float(row['stop_lon']), float(row['stop_lat'])),
                            common_name=row['stop_name'][:48],
                            locality_centre=False,
                            admin_area_id=row['stop_id'][:3],
                            active=True
                        )
            with archive.open('agency.txt') as csv_file:
                for row in get_rows(csv_file):
                    agencies[row['agency_id']] = row
            with archive.open('routes.txt') as csv_file:
                for row in get_rows(csv_file):
                    routes[row['route_id']] = row
                    routes[row['route_id']]['trips'] = []
            with archive.open('trips.txt') as csv_file:
                for row in get_rows(csv_file):
                    trips[row['trip_id']] = row
                    trips[row['trip_id']]['stop_times'] = []
                    routes[row['route_id']]['trips'].append(row)
            with archive.open('stop_times.txt') as csv_file:
                for row in get_rows(csv_file):
                    trips[row['trip_id']]['stop_times'].append(row)

        for route in routes.values():
            defaults = {
                'region_id': 'LE',
                'line_name': route['route_short_name'],
                'description': route['route_long_name'],
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES.get(route['route_type'], ''),
                'current': True
            }
            if route['trips']:
                for trip in route['trips']:
                    if not defaults['description']:
                        defaults['description'] = trip['trip_headsign'].strip()
                    if trip['direction_id'] == '0' and not defaults.get('outbound_description'):
                        defaults['outbound_description'] = trip['trip_headsign'].strip()
                    elif trip['direction_id'] == '1' and not defaults.get('inbound_description'):
                        defaults['inbound_description'] = trip['trip_headsign'].strip()
            else:
                break

            route_id = route['route_id'].split()[0]
            service, created = Service.objects.update_or_create(
                service_code='{}-{}'.format(collection, '-'.join(route_id.split('-')[:-1])),
                defaults=defaults
            )
            # if not created:
            #     print(service)
            if route['agency_id']:
                operator = Operator.objects.get_or_create(name=agencies[route['agency_id']]['agency_name'], defaults={
                    'id': route['agency_id'],
                    'region_id': 'LE',
                    'vehicle_mode': defaults['mode']
                })[0]
                service.operator.add(operator)
                operators.add(operator)

            outbound_stops = {}
            inbound_stops = {}
            for trip in route['trips']:
                if trip['direction_id'] == '0':
                    stops = outbound_stops
                    direction = 'Outbound'
                else:
                    stops = inbound_stops
                    direction = 'Inbound'
                for stop in trip['stop_times']:
                    if StopPoint.objects.filter(atco_code=stop['stop_id']).exists():
                        stops[stop['stop_id']] = StopUsage(
                            service=service,
                            stop_id=stop['stop_id'],
                            order=stop['stop_sequence'],
                            direction=direction
                        )
                    else:
                        print(stop['stop_id'])
            StopUsage.objects.bulk_create(outbound_stops.values())
            StopUsage.objects.bulk_create(inbound_stops.values())

            service.region = Region.objects.filter(adminarea__stoppoint__service=service).annotate(
                Count('adminarea__stoppoint__service')
            ).order_by('-adminarea__stoppoint__service__count').first()
            if service.region_id:
                service.save()

        for operator in operators:
            operator.region = Region.objects.filter(adminarea__stoppoint__service__operator=operator).annotate(
                Count('adminarea__stoppoint__service__operator')
            ).order_by('-adminarea__stoppoint__service__operator__count').first()
            if operator.region_id:
                operator.save()

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Import data even if the GTFS feeds haven\'t changed')

    def handle(self, *args, **options):
        session = requests.Session()

        for collection in COLLECTIONS:
            if options['verbosity'] > 1:
                print(collection)
            path = 'google_transit_{}.zip'.format(collection)
            url = 'http://www.transportforireland.ie/transitData/' + path
            path = 'data/' + path
            if os.path.exists(path):
                response = session.get(url, headers={
                    'if-modified-since': time.ctime(os.path.getmtime(path) - 3600)
                }, stream=True)
                if response.status_code != 304:
                    write_zip_file(path, response)
                elif not options['force']:
                    continue
            else:
                write_zip_file(path, session.get(url, stream=True))
            self.handle_zipfile(path, collection)
