import requests
from django.contrib.gis.geos import Point, LineString, MultiLineString
from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import Region, Service, Operator, StopPoint
from .import_guernsey import import_stops, import_routes


class Command(BaseCommand):
    def import_routes(self, session):
        for route in session.get(
            'http://sojbuslivetimespublic.azurewebsites.net/api/values/getroutes'
        ).json()['routes']:
            service = Service.objects.filter(service_code='je-{}'.format(route['Number'])).first()
            if service:
                outbound = []
                inbound = []
                for point in route['RouteCoordinates']:
                    (outbound if point['direction'] == 'O' else inbound).append(Point(point['lon'], point['lat']))
                service.geometry = MultiLineString(LineString(outbound), LineString(inbound))
                service.save()

    @transaction.atomic
    def handle(self, *args, **options):

        region = Region.objects.update_or_create(id='JE', defaults={'name': 'Jersey'})[0]
        operator = Operator.objects.update_or_create(id='libertybus', name='Liberty Bus', region=region)[0]

        import_stops(region)

        session = requests.Session()

        Service.objects.filter(region=region).update(current=False)

        import_routes(region, operator, 'https://libertybus.je/routes_times/timetables', session)

        self.import_routes(session)

        StopPoint.objects.filter(atco_code__startswith='gg-').exclude(service__current=True).delete()
