import os
import time
import requests
from email.utils import parsedate
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.conf import settings
from multigtfs.models import Feed
from txc.ie import get_timetables
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
        response = SESSION.head(url, headers=headers, stream=True)
        if response.status_code == 304 or parsedate(response.headers['last-modified']) <= last_modified:
            return False  # not modified
    response = SESSION.get(url, stream=True)
    write_zip_file(path, response)
    return True


class Command(BaseCommand):
    @transaction.atomic
    def handle_zipfile(self, archive_name, collection):
        if len(collection) > 10:
            collection = collection[:10]
            Service.objects.filter(service_code__startswith=collection).delete()
        else:
            Service.objects.filter(service_code__startswith=collection + '-').delete()

        operators = set()

        feed = Feed.objects.create(name=collection)
        feed.import_gtfs(archive_name)

        for stop in feed.stop_set.all():
            if stop.stop_id[0] in '78' and not StopPoint.objects.filter(atco_code=stop.stop_id).exists():
                StopPoint.objects.create(
                    atco_code=stop.stop_id,
                    latlong=stop.point,
                    common_name=stop.name[:48],
                    locality_centre=False,
                    admin_area_id=stop.stop_id[:3],
                    active=True
                )

        routes = {}
        for route in feed.route_set.all():
            route_id = '-'.join(route.route_id.split(' ', 1)[0].split('-')[:-1])
            routes[route_id] = route

        for route_id in routes:
            service_code = collection + '-' + route_id
            timetable = get_timetables(service_code, None)[0]

            if not timetable.groupings:
                continue

            route = routes[route_id]

            defaults = {
                'region_id': 'LE',
                'line_name': route.short_name,
                'description': route.long_name or timetable.groupings[0].name,
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES.get(route.rtype, ''),
                'current': True
            }
            service, created = Service.objects.update_or_create(
                service_code=service_code,
                defaults=defaults
            )

            if route.agency:
                operator = Operator.objects.get_or_create(name=route.agency.name, defaults={
                    'id': route.agency.agency_id,
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
                direction = 'Inbound'
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
        for collection in settings.IE_COLLECTIONS:
            if options['verbosity'] > 1:
                print(collection)
            path = 'google_transit_{}.zip'.format(collection)
            url = 'http://www.transportforireland.ie/transitData/' + path
            path = os.path.join(settings.DATA_DIR, path)
            modified = download_if_modified(path, url)
            if modified or options['force']:
                self.handle_zipfile(path, collection)
