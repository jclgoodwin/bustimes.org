import time
from django.core.management.base import BaseCommand
from django.db import transaction
from multigtfs.models import Feed
from txc.ie import get_timetable
from ...models import Operator, Service, StopPoint, StopUsage, Region
from .import_ie_gtfs import download_if_modified, MODES


class Command(BaseCommand):
    @staticmethod
    def get_stop_id(collection, stop):
        stop_id = stop.stop_id
        if stop_id.lower().startswith(collection.lower() + ':'):
            stop_id = stop_id.split(':')[1]
        return '{}-{}'.format(collection, stop_id)

    @staticmethod
    def get_stop_name(row):
        stop_name = row.name
        parts = stop_name.split(', ')
        if len(parts) == 2:
            if parts[1].lower().startswith(parts[0].lower()):
                return parts[1]
            if parts[1].lower() in parts[0].lower():
                return parts[0]
        return stop_name[:48]

    @staticmethod
    def get_service_id(collection, row):
        service_id = row.route_id
        if service_id.lower().startswith(collection.lower() + ':'):
            service_id = service_id.split(':')[1]
        return '{}-{}'.format(collection, service_id)

    @classmethod
    @transaction.atomic
    def handle_zipfile(cls, archive_name, collection):
        Service.objects.filter(service_code__startswith=collection).delete()

        Feed.objects.filter(name=collection).delete()

        feed = Feed.objects.create(name=collection)
        feed.import_gtfs(archive_name)

        for stop in feed.stop_set.all():
            StopPoint.objects.update_or_create(atco_code=cls.get_stop_id(collection, stop), defaults={
                'common_name': cls.get_stop_name(stop),
                'naptan_code': stop.code,
                'latlong': stop.point,
                'locality_centre': False,
                'active': True
            })

        for route in feed.route_set.all():
            service_id = cls.get_service_id(collection, route)

            timetable = get_timetable([route], None)

            defaults = {
                'region_id': 'FR',
                'line_name': route.short_name,
                'description': route.long_name,
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES[route.rtype],
                'current': True
            }

            service, created = Service.objects.update_or_create(
                service_code=service_id,
                defaults=defaults
            )

            operator = Operator.objects.get_or_create(name=route.agency.name, defaults={
                'id': route.agency_id,
                'region_id': 'FR',
                'vehicle_mode': defaults['mode'],
                'phone': route.agency.phone,
                'url': route.agency.url,
                # 'email': route.agency.email or '',
            })[0]
            service.operator.add(operator)

            direction = 'Outbound'
            stops = []
            for grouping in timetable.groupings:
                for i, row in enumerate(grouping.rows):
                    stop_id = row.part.stop.atco_code
                    if stop_id.lower().startswith(collection + ':'):
                        stop_id = collection + '-' + stop_id.split(':', 1)[1]
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

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Import data even if the GTFS feeds haven\'t changed')

    def handle(self, *args, **options):
        Region.objects.update_or_create(id='FR', name='France')

        force = options['force']

        if download_if_modified('flixbus-eu.zip', 'http://data.ndovloket.nl/flixbus/flixbus-eu.zip') or force:
            self.handle_zipfile('flixbus-eu.zip', 'flixbus')
        if download_if_modified('ouibus.zip', 'https://api.idbus.com/gtfs.zip') or force:
            self.handle_zipfile('ouibus.zip', 'ouibus')
