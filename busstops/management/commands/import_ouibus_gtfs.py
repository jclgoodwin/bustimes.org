import time
import zipfile
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import Operator, Service, StopPoint, StopUsage, Region
from .import_ie_gtfs import get_rows, download_if_modified, MODES


class Command(BaseCommand):
    @staticmethod
    def get_stop_id(collection, row):
        stop_id = row['stop_id']
        if stop_id.lower().startswith(collection.lower() + ':'):
            stop_id = stop_id.split(':')[1]
        return '{}-{}'.format(collection, stop_id)

    @staticmethod
    def get_stop_name(row):
        stop_name = row['stop_name']
        parts = stop_name.split(', ')
        if len(parts) == 2:
            if parts[1].lower().startswith(parts[0].lower()):
                return parts[1]
            if parts[1].lower() in parts[0].lower():
                return parts[0]
        return stop_name[:48]

    @staticmethod
    def get_service_id(collection, row):
        service_id = row['route_id']
        if service_id.lower().startswith(collection.lower() + ':'):
            service_id = service_id.split(':')[1]
        return '{}-{}'.format(collection, service_id)

    @classmethod
    @transaction.atomic
    def handle_zipfile(cls, archive_name, collection):
        collection = collection[:10]
        Service.objects.filter(service_code__startswith=collection).update(current=False)

        routes = {}
        trips = {}
        agencies = {}
        with zipfile.ZipFile(archive_name) as archive:
            with archive.open('stops.txt') as csv_file:
                for row in get_rows(csv_file):
                    print(row)
                    StopPoint.objects.update_or_create(atco_code=cls.get_stop_id(collection, row), defaults={
                        'common_name': cls.get_stop_name(row),
                        'naptan_code': row['stop_code'],
                        'latlong': Point(float(row['stop_lon']), float(row['stop_lat'])),
                        'locality_centre': False,
                        'active': True
                    })
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
                'region_id': 'FR',
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

            service, created = Service.objects.update_or_create(
                service_code=cls.get_service_id(collection, route),
                defaults=defaults
            )
            if route['agency_id']:
                agency = agencies[route['agency_id']]
                operator = Operator.objects.get_or_create(name=agency['agency_name'], defaults={
                    'id': route['agency_id'],
                    'region_id': 'FR',
                    'vehicle_mode': defaults['mode'],
                    'phone': agency['agency_phone'],
                    'url': agency['agency_url'],
                    'email': agency.get('agency_email', ''),
                })[0]
                service.operator.add(operator)

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
                    atco_code = cls.get_stop_id(collection, stop)
                    if StopPoint.objects.filter(atco_code=atco_code).exists():
                        stops[stop['stop_id']] = StopUsage(
                            service=service,
                            stop_id=atco_code,
                            order=stop['stop_sequence'],
                            direction=direction
                        )
                    else:
                        print(stop['stop_id'])
            StopUsage.objects.bulk_create(outbound_stops.values())
            StopUsage.objects.bulk_create(inbound_stops.values())

    def handle(self, *args, **options):
        Region.objects.update_or_create(id='FR', name='France')

        if download_if_modified('flixbus-eu.zip', 'http://data.ndovloket.nl/flixbus/flixbus-eu.zip'):
            self.handle_zipfile('flixbus-eu.zip', 'flixbus')
        if download_if_modified('ouibus.zip', 'https://api.idbus.com/gtfs.zip'):
            self.handle_zipfile('ouibus.zip', 'ouibus')
