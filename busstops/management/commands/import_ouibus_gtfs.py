import os
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from titlecase import titlecase
from multigtfs.models import Feed, ServiceDate, Service as GTFSService
from txc.ie import get_grouping_name_part, get_timetable
from ...models import Operator, Service, StopPoint, StopUsage, Region
from .import_ie_gtfs import download_if_modified, MODES


class Command(BaseCommand):
    @staticmethod
    def get_stop_id(collection, stop_id):
        if stop_id.lower().startswith(collection.lower() + ':'):
            stop_id = stop_id.split(':')[1]
        return '{}-{}'.format(collection, stop_id)

    @staticmethod
    def get_stop_name(stop_name):
        stop_name = get_grouping_name_part(stop_name)[:48]
        if stop_name.isupper():
            stop_name = titlecase(stop_name)
        return stop_name

    @staticmethod
    def get_service_id(collection, service_id):
        if service_id.lower().startswith(collection.lower() + ':'):
            service_id = service_id.split(':')[1]
        return '{}-{}'.format(collection, service_id)

    @classmethod
    @transaction.atomic
    def handle_zipfile(cls, archive_name, collection):
        Service.objects.filter(service_code__startswith=collection).delete()
        StopPoint.objects.filter(atco_code__startswith=collection).delete()

        Feed.objects.filter(name=collection).delete()

        feed = Feed.objects.create(name=collection)

        feed.import_gtfs(archive_name)

        for stop in feed.stop_set.filter(stoptime__isnull=False).distinct():
            defaults = {
                'common_name': cls.get_stop_name(stop.name),
                'naptan_code': stop.code,
                'latlong': stop.point,
                'locality_centre': False,
                'active': True,
                'town': stop.extra_data.get('stop_town', '')
            }
            if collection == 'flixbus':
                defaults['crossing'] = stop.desc.split(',')[0][:48]
            elif collection == 'metz':
                defaults['indicator'] = stop.desc or stop.code
            StopPoint.objects.update_or_create(atco_code=cls.get_stop_id(collection, stop.stop_id), defaults=defaults)

        today = datetime.now().date()

        for route in feed.route_set.select_related('agency'):
            end_date = GTFSService.objects.filter(trip__route=route,
                                                  end_date__isnull=False).order_by('-end_date').first()
            if end_date:
                end_date = end_date.end_date
            else:
                end_date = ServiceDate.objects.filter(service__trip__route=route,
                                                      exception_type=1).order_by('-date').first()
                if end_date:
                    end_date = end_date.date

            if end_date and end_date < today:
                continue

            service_id = cls.get_service_id(collection, route.route_id)

            timetable = get_timetable([route], collection=collection)

            if not timetable.groupings:
                continue

            defaults = {
                'region_id': 'FR',
                'line_name': route.short_name,
                'description': route.long_name,
                'date': time.strftime('%Y-%m-%d'),
                'mode': MODES[route.rtype],
                'current': True,
                'outbound_description': timetable.groupings[0].name,
            }
            if len(timetable.groupings) > 1:
                defaults['inbound_description'] = timetable.groupings[1]
            if defaults['description'].isupper():
                defaults['description'] = titlecase(defaults['description'])

            service, created = Service.objects.update_or_create(
                service_code=service_id,
                defaults=defaults
            )

            if not route.agency:
                route.agency = feed.agency_set.get()
            operator = Operator.objects.get_or_create(name=route.agency.name, defaults={
                'id': route.agency_id,
                'region_id': 'FR',
                'vehicle_mode': defaults['mode'],
                'phone': route.agency.phone,
                'url': route.agency.url,
                # 'email': route.agency.email or '',
            })[0]
            service.operator.add(operator)

            stops = []
            direction = 'Outbound'
            for grouping in timetable.groupings:
                for i, row in enumerate(grouping.rows):
                    stops.append(
                        StopUsage(
                            service=service,
                            stop_id=row.part.stop.atco_code,
                            order=i,
                            direction=direction
                        )
                    )
                direction = 'Inbound'
            StopUsage.objects.bulk_create(stops)

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Import data even if the GTFS feeds haven\'t changed')

    def handle(self, *args, **options):
        Region.objects.update_or_create(id='FR', name='France')

        force = options['force']

        for collection in settings.FRANCE_COLLECTIONS:
            path = os.path.join(settings.DATA_DIR, collection) + '.zip'
            if download_if_modified(path, settings.FRANCE_COLLECTIONS[collection]) or force:
                self.handle_zipfile(path, collection)
