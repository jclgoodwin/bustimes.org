from os.path import join
from datetime import date
from urllib.parse import urlencode
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone
from multigtfs.models import Feed, Stop
from ...models import Region, Operator, Service, ServiceCode, DataSource, StopPoint, StopUsage
from .import_ie_gtfs import download_if_modified, get_timetable


class Command(BaseCommand):
    @staticmethod
    def process_gtfs(collection, feed):
        scheme = f'{collection} GTFS'
        ServiceCode.objects.filter(scheme=scheme).delete()
        source, created = DataSource.objects.get_or_create(name=scheme)
        today = date.today()

        source = DataSource.objects.update_or_create({'datetime': timezone.now()}, name=scheme)[0]
        source.service_set.update(current=False)

        Region.objects.get_or_create(name='France', id='FR')

        if collection == 'hi':
            thebus = Operator.objects.update_or_create(id='thebus', name='TheBus', region_id='HI')[0]

        for route in feed.route_set.all():
            if collection == 'hi':
                route.long_name = route.long_name.replace('-', ' - ')
                region = 'HI'
            elif collection == 'fr-nor':
                if route.agency.name != 'Manéo (Manche)':
                    continue
                region = 'FR'

            print(route.route_id)
            # continue
            service = Service.objects.update_or_create(
                {
                    'source': source,
                    'line_name': route.short_name,
                    'description': route.long_name,
                    'current': True,
                    'date': today,
                    'region_id': region,
                    'show_timetable': True,
                    'geometry': route.geometry
                },
                service_code=f'{collection}-{route.route_id}'
            )[0]

            if collection == 'fr-nor':
                timetable = get_timetable((route,), None)

                direction = 'Outbound'
                stops = []
                for grouping in timetable.groupings:
                    for i, row in enumerate(grouping.rows):
                        stop_id = row.part.stop.atco_code
                        if not StopPoint.objects.filter(atco_code=stop_id).exists():
                            StopPoint.objects.create(atco_code=stop_id, common_name=row.part.stop.name, active=True)
                        stops.append(
                            StopUsage(
                                service=service,
                                stop_id=stop_id,
                                order=i,
                                direction=direction
                            )
                        )
                    direction = 'Inbound'

                for stop in Stop.objects.filter(stoptime__trip__route=route).distinct():
                    StopPoint.objects.filter(pk=stop.stop_id).update(latlong=Point(stop.lon, stop.lat))
                StopUsage.objects.bulk_create(stops)

            if collection == 'hi':
                service.operator.add(thebus)
            else:
                try:
                    operator_code = f'{collection}-{route.agency.agency_id}'
                    operator, operator_created = Operator.objects.get_or_create(id=operator_code,
                                                                                name=route.agency.name,
                                                                                region_id=region)
                except Exception as e:
                    print(route.agency.agency_id, e)
                service.operator.add(operator)
            ServiceCode.objects.update_or_create(
                service=service,
                scheme=scheme,
                code=route.route_id
            )

    @classmethod
    def handle_collection(cls, collection, url):
        archive_name = join(settings.DATA_DIR, 'google_transit_{}.zip'.format(collection))
        modified = download_if_modified(archive_name, url)

        if not modified:
            return

        with transaction.atomic():
            feed = Feed.objects.create(name=collection)
            feed.import_gtfs(archive_name)

            if collection in {'hi', 'fr-nor'}:
                cls.process_gtfs(collection, feed)

        Feed.objects.filter(name=collection).exclude(id=feed.id).delete()

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Import data even if the GTFS feeds haven\'t changed')

    def handle(self, *args, **options):
        # Hawaii
        self.handle_collection('hi', 'http://webapps.thebus.org/transitdata/Production/google_transit.zip')

        # West Midlands
        self.handle_collection('tfwm', 'http://api.tfwm.org.uk/gtfs/tfwm_gtfs.zip?' + urlencode(settings.TFWM))

        self.handle_collection('fr-nor', 'https://www.data.gouv.fr/fr/datasets/r/864ea8e4-97f0-4f12-8b5a-e6a806eae139')
