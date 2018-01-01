import requests
from datetime import date
from django.db import IntegrityError
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from ...models import Region, StopPoint, Service, StopUsage, Operator


class Command(BaseCommand):
    def handle_stop(self, stop):
        stop_code = 'sg-' + stop['BusStopCode']
        name = stop['Description']
        # http://landtransportguru.net/acronyms/
        for abbreviation, replacement in (
            ('Opp', 'Opposite'),
            ('Aft', 'After'),
            ('Bef', 'Before'),
            ("S'pore", 'Singapore'),
            ('Ctr', 'Centre'),
            ('Blk', 'Block'),
            ('Int', 'Interchange'),
            ('Stn', 'Station'),
            ('Upp', 'Upper'),
            ('Rd', 'Road'),
            ('Condo', 'Condominium'),
            ('Ch', 'Church'),
            ('Ind Pk', 'Industrial Park'),
            ('Sci Pk', 'Science Park'),
            ('Pk', 'Park'),
            ('Bldg', 'Building'),
            ('Ctrl', 'Central'),
            ('Sec Sch', 'Secondary School'),
            ('Gdn', 'Garden'),
            ('Gdns', 'Gardens'),
            ('Pt', 'Point'),
            ('St', 'Street'),
            ('Dr', 'Drive'),
        ):
            name = name.replace(abbreviation + ' ', replacement + ' ', 1)
            name = name.replace(abbreviation + '/', replacement + '/', 1)
            if name.endswith(abbreviation):
                name = name.replace(abbreviation, replacement, 1)
        StopPoint.objects.update_or_create(
            atco_code=stop_code,
            defaults={
                'common_name': name,
                'street': stop['RoadName'],
                'crossing': '',
                'locality_centre': False,
                'active': True,
                'latlong': Point(stop['Longitude'], stop['Latitude'])
            }
        )

    def handle(self, *args, **options):
        self.session = requests.Session()
        self.session.headers = {
            'AccountKey': settings.SINGAPORE_KEY
        }
        today = date.today()

        Region.objects.update_or_create(id='SG', defaults={'name': 'Singapore'})

        for code, name in (
            ('SBST', 'SBS Transit'),
            ('TTS', 'Tower Transit Singapore'),
            ('SMRT', 'SMRT'),
            ('GAS',  'Go-Ahead Singapore'),
        ):
            Operator.objects.update_or_create(id=code, defaults={'name': name, 'region_id': 'SG',
                                                                 'vehicle_mode': 'bus'})

        skip = 0
        while True:
            res = self.session.get('http://datamall2.mytransport.sg/ltaodataservice/BusStops', params={
                '$skip': skip
            })
            stops = res.json()['value']
            for stop in stops:
                self.handle_stop(stop)
            if len(stops) < 500:
                break
            skip += len(stops)

        res = self.session.get('http://datamall2.mytransport.sg/ltaodataservice/BusServices')
        for service in res.json()['value']:
            print(service)

        skip = 0
        while True:
            res = self.session.get('http://datamall2.mytransport.sg/ltaodataservice/BusRoutes', params={
                '$skip': skip
            })
            routes = res.json()['value']
            for route in routes:
                service_code = 'sg-{}-{}'.format(route['Operator'], route['ServiceNo']).lower()
                service = Service.objects.update_or_create(service_code=service_code, defaults={
                    'slug': service_code,
                    'date': today,
                    'region_id': 'SG',
                    'mode': 'bus',
                    'line_name': route['ServiceNo'],
                    'operator': [route['Operator']]
                })[0]

                try:
                    StopUsage.objects.update_or_create(
                        service=service,
                        stop_id='sg-' + route['BusStopCode'],
                        order=route['StopSequence'],
                        defaults={
                            'direction': route['Direction']
                        }
                    )
                except IntegrityError:
                    print(route)

            if len(routes) < 500:
                break
            skip += len(routes)
