import os
import time
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.conf import settings
from multigtfs.models import Feed
from timetables.gtfs import get_timetables
from ...models import Operator, Service, StopPoint, StopUsage, Region


MODES = {
    0: 'tram',
    2: 'rail',
    3: 'bus',
    4: 'ferry'
}
SESSION = requests.Session()


class Command(BaseCommand):
    @transaction.atomic
    def handle_zipfile(self, archive_name, collection):
        print(archive_name, collection)

        Service.objects.filter(service_code__startswith=collection + '-').delete()

        operators = set()

        feed = Feed.objects.filter(name=collection).last()
        if not feed:
            feed = Feed.objects.create(name=collection)
            feed.import_gtfs(archive_name)

        for route in feed.route_set.all():
            service_code = collection + '-' + route.route_id
            timetable = get_timetables(service_code, None)[0]

            if not timetable.groupings:
                continue

            defaults = {
                'region_id': 'L',
                'line_name': route.short_name,
                'line_brand': route.long_name,
                'description': route.desc,
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
                    'region_id': 'L',
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
        for collection in ('citymapper',):
            path = '{}.zip'.format(collection)
            path = os.path.join(settings.DATA_DIR, path)
            self.handle_zipfile(path, collection)
