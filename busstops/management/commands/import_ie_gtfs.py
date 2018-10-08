import os
import time
import requests
from email.utils import parsedate
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.conf import settings
from multigtfs.models import Feed, StopTime, Stop
from timetables.gtfs import get_stop_id, get_timetable
from ...models import Operator, Service, StopPoint, StopUsage, Region, ServiceCode


MODES = {
    0: 'tram',
    2: 'rail',
    3: 'bus',
    4: 'ferry',
    200: 'coach',
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
        response = SESSION.head(url, headers=headers, timeout=5)
        if response.status_code == 304:
            return False  # not modified
        if 'last-modified' in response.headers and parsedate(response.headers['last-modified']) <= last_modified:
            return False
    response = SESSION.get(url, stream=True)
    write_zip_file(path, response)
    return True


class Command(BaseCommand):
    @transaction.atomic
    def handle_zipfile(self, archive_name, collection):
        Service.objects.filter(service_code__startswith=collection + '-').update(current=False)
        StopUsage.objects.filter(service__service_code__startswith=collection + '-').delete()
        ServiceCode.objects.filter(service__service_code__startswith=collection + '-').delete()

        operators = set()

        feed = Feed.objects.filter(name=collection).delete()
        feed = Feed.objects.create(name=collection)
        feed.import_gtfs(archive_name)

        if collection == 'sro':
            roscommon_mart_road = Stop.objects.get(stop_id='850000013')
            stop_times = StopTime.objects.filter(stop__feed=feed, trip__route__agency__name='Brendan Boyle')
            stop_times.filter(stop__stop_id='850000014').update(stop=roscommon_mart_road)
            stop_times.filter(stop__stop_id='850000015').update(stop=roscommon_mart_road)

        for stop in feed.stop_set.all():
            stop_id = get_stop_id(stop.stop_id)
            if stop_id[0] in '78' and len(stop_id) <= 16:
                if not StopPoint.objects.filter(atco_code=stop_id).exists():
                    StopPoint.objects.create(
                        atco_code=stop_id,
                        latlong=stop.point,
                        common_name=stop.name[:48],
                        locality_centre=False,
                        admin_area_id=stop_id[:3],
                        active=True
                    )
            else:
                print(stop_id)

        for route in feed.route_set.all():
            if route.short_name and len(route.short_name) <= 8:
                route_id = route.short_name
            elif route.long_name and len(route.long_name) <= 4:
                route_id = route.long_name
            else:
                route_id = route.route_id.split()[0]

            if collection == 'eurobus':
                service_code = 'dublincoach' + '-' + route_id
            else:
                service_code = collection + '-' + route_id
            assert len(service_code) <= 24

            timetable = get_timetable((route,), None)

            if not timetable.groupings:
                continue

            defaults = {
                'region_id': 'LE',
                'line_name': route.short_name,
                'description': route.long_name or timetable.groupings[0].name,
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES.get(route.rtype, ''),
                'current': True,
                'show_timetable': True
            }
            service, created = Service.objects.update_or_create(
                service_code=service_code,
                defaults=defaults
            )
            ServiceCode.objects.create(service=service, scheme=collection + ' GTFS', code=route.route_id)

            if route.agency:
                operator, created = Operator.objects.get_or_create({
                    'name': route.agency.name,
                    'region_id': 'LE',
                    'vehicle_mode': defaults['mode']
                }, id=route.agency.id, region__in=['CO', 'UL', 'MU', 'LE', 'NI'])
                if not created and operator.name != route.agency.name:
                    print(operator.name, route.agency.name)
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
            url = 'https://www.transportforireland.ie/transitData/' + path
            path = os.path.join(settings.DATA_DIR, path)
            modified = download_if_modified(path, url)
            if modified or options['force']:
                print(collection)
                self.handle_zipfile(path, collection)
