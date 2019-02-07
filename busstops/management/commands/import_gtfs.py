from datetime import date
from urllib.parse import urlencode
from django.core.management.base import BaseCommand
from django.conf import settings
from multigtfs.models import Feed
from ...models import Operator, Service, ServiceCode
from .import_ie_gtfs import download_if_modified


class Command(BaseCommand):
    urls = {
        'hi': 'http://webapps.thebus.org/transitdata/Production/google_transit.zip',
        'tfwm': 'http://api.tfwm.org.uk/gtfs/tfwm_gtfs.zip?' + urlencode(settings.TFWM),
    }

    @classmethod
    def handle_collection(cls, collection):
        archive_name = 'google_transit_{}.zip'.format(collection)
        modified = download_if_modified(archive_name, cls.urls[collection])

        if not modified:
            return

        Feed.objects.filter(name=collection).delete()
        feed = Feed.objects.create(name=collection)
        feed.import_gtfs(archive_name)

        if collection != 'hi':
            return

        scheme = '{} GTFS'.format(collection)
        ServiceCode.objects.filter(scheme=scheme).delete()

        thebus = Operator.objects.update_or_create(id='thebus', name='TheBus', region_id='HI')[0]

        for route in feed.route_set.all():
            if collection == 'hi':
                route.long_name = route.long_name.replace('-', ' - ')
            service = Service.objects.update_or_create(
                {
                    'line_name': route.short_name,
                    'description': route.long_name,
                    'date': date.today(),
                    'region_id': 'HI',
                    'show_timetable': True
                },
                service_code='{}-{}'.format(collection, route.short_name)
            )[0]
            service.operator.add(thebus)
            ServiceCode.objects.update_or_create(
                service=service,
                scheme=scheme,
                code=route.route_id
            )
            print(route, route.short_name, route.long_name)

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Import data even if the GTFS feeds haven\'t changed')

    def handle(self, *args, **options):
        # hawaii
        self.handle_collection('hi')
        self.handle_collection('tfwm')
