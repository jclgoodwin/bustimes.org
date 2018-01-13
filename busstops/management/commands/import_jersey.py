import requests
from time import sleep
from datetime import date
from django.contrib.gis.geos import Point, LineString, MultiLineString
from django.core.management.base import BaseCommand
from ...models import Region, StopPoint, Service, StopUsage, Operator


class Command(BaseCommand):
    def import_stops(self, session):
        for stop in session.get(
            'http://sojbuslivetimespublic.azurewebsites.net/api/values/0/49/-2/1000000000/1000000000'
        ).json()['stops']:
            StopPoint.objects.update_or_create(
                atco_code='je-{}'.format(stop['StopNumber']),
                defaults={
                    'common_name': stop['StopName'],
                    'naptan_code': stop['StopNumber'],
                    'latlong': Point(stop['Longitude'], stop['Latitude']),
                    'locality_centre': False,
                    'active': True,
                }
            )

    def import_routes(self, session, region):
        today = date.today()
        operator = Operator.objects.update_or_create(id='libertybus', name='Liberty Bus', region=region)[0]
        for route in session.get(
            'http://sojbuslivetimespublic.azurewebsites.net/api/values/getroutes'
        ).json()['routes']:
            outbound = []
            inbound = []
            for point in route['RouteCoordinates']:
                (outbound if point['direction'] == 'O' else inbound).append(Point(point['lon'], point['lat']))
            Service.objects.update_or_create(service_code='je-{}'.format(route['Number']), defaults={
                'date': today,
                'line_name': route['Number'],
                'description': route['Name'],
                'region': region,
                'mode': 'bus',
                'operator': [operator],
                'geometry': MultiLineString(LineString(outbound), LineString(inbound))
            })

    def import_stop_routes(self, session):
        for stop in StopPoint.objects.filter(atco_code__startswith='je-'):
            for departure in session.get(
                'http://sojbuslivetimespublic.azurewebsites.net/api/values/busstop/{}'.format(stop.naptan_code)
            ).json():
                assert str(departure['StopNumber']) == stop.naptan_code
                service_id = 'je-{}'.format(departure['ServiceNumber'])
                StopUsage.objects.update_or_create(service_id=service_id, order=0, stop=stop,
                                                   direction=departure['Destination'][:8])
            sleep(1)

    def handle(self, *args, **options):
        session = requests.Session()

        region = Region.objects.update_or_create(id='JE', defaults={'name': 'Jersey'})[0]

        self.import_stops(session)

        self.import_routes(session, region)

        self.import_stop_routes(session)
