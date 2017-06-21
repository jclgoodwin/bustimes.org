import os
import time
import pygtfs
import requests
from email.utils import parsedate
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from txc.ie import COLLECTIONS, get_schedule, get_feed, get_timetable
from ...models import Operator, Service, StopPoint, StopUsage, Region


MODES = {
    2: 'rail',
    3: 'bus',
    4: 'ferry'
}
SESSION = requests.Session()


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
        response = SESSION.get(url, headers=headers, stream=True)
        if response.status_code == 304 or parsedate(response.headers['last-modified']) <= last_modified:
            return False  # not modified
    else:
        response = SESSION.get(url, stream=True)
    write_zip_file(path, response)
    return True


class Command(BaseCommand):
    @transaction.atomic
    def handle_zipfile(self, archive_name, collection):
        collection = collection[:10]
        Service.objects.filter(service_code__startswith=collection).delete()

        # agencies = {}
        operators = set()

        schedule = get_schedule()
        pygtfs.append_feed(schedule, archive_name)  # this could take a while :(

        feed = get_feed(schedule, archive_name)
        for stop in feed.stops:
            if stop.id[0] in '78' and not StopPoint.objects.filter(atco_code=stop.id).exists():
                StopPoint.objects.create(
                    atco_code=stop.id,
                    latlong=Point(float(stop.stop_lon), float(stop.stop_lat)),
                    common_name=stop.stop_name[:48],
                    locality_centre=False,
                    admin_area_id=stop.id[:3],
                    active=True
                )

        routes = {}
        for route in feed.routes:
            route_id = '-'.join(route.id.split('-')[-1])
            routes[route_id] = route

        for route_id in routes:
            service_code = collection + '-' + route_id
            timetable = get_timetable(service_code, None)[0]

            route = routes[route_id]

            defaults = {
                'region_id': 'LE',
                'line_name': route.route_short_name,
                'description': route.route_long_name or timetable.groupings[0].name,
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES.get(route.route_type, ''),
                'current': True
            }
            service, created = Service.objects.update_or_create(
                service_code=service_code,
                defaults=defaults
            )

            if not created:
                print(service)

            operator = Operator.objects.get_or_create(name=route.agency.agency_name, defaults={
                'id': route.agency_id,
                'region_id': 'LE',
                'vehicle_mode': defaults['mode']
            })[0]
            service.operator.add(operator)
            operators.add(operator)

            direction = 'Outbound'
            stops = []
            for grouping in timetable.groupings:
                for i, row in enumerate(grouping.rows):
                    stop_id = row.part.stop.atco_code
                    if StopPoint.objects.filter(atco_code=stop_id).exists():
                        stops.append(
                            StopUsage(
                                service=service,
                                stop_id=stop_id,
                                order=i,
                                direction=direction
                            )
                        )
                    else:
                        print(stop_id)
            StopUsage.objects.bulk_create(stops)

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
        for collection in COLLECTIONS:
            if options['verbosity'] > 1:
                print(collection)
            path = 'google_transit_{}.zip'.format(collection)
            url = 'http://www.transportforireland.ie/transitData/' + path
            path = 'data/' + path
            modified = download_if_modified(path, url)
            if modified or options['force']:
                self.handle_zipfile(path, collection)
