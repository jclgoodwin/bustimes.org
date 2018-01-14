import os
import json
import requests
from time import sleep
from datetime import date
from bs4 import BeautifulSoup
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from ...models import Region, StopPoint, Service, StopUsage, Operator


DIR = os.path.dirname(__file__)


class Command(BaseCommand):
    def import_stops(self):
        with open(os.path.join(DIR, '../../../data/guernsey.json')) as open_file:
            records = json.load(open_file)
            for zoom_level in records:
                for place in zoom_level['places']:
                    assert place['icon'] == ['stop', 'flag-shadow']
                    name, stop_code = place['name'].split('\n')
                    assert stop_code.startswith('Bus stop code - 890000')
                    stop_code = stop_code.split()[-1]
                    defaults = {
                        'common_name': name,
                        'naptan_code': stop_code,
                        'latlong': Point(*place['posn'][::-1]),
                        'locality_centre': False,
                        'active': True,
                    }
                    if ', ' in name:
                        defaults['common_name'], defaults['indicator'] = name.split(', ')
                    StopPoint.objects.update_or_create(defaults, atco_code='gg-{}'.format(stop_code))

    def import_routes(self, session, region):
        today = date.today()
        operator = Operator.objects.update_or_create(id='guernsey', name='Guernsey Buses', region=region)[0]
        res = session.get('http://m.buses.gg/Timetables')
        soup = BeautifulSoup(res.text, 'lxml')
        for li in soup.find(id='timetables-ul').find_all('li'):
            line_name = li.find(class_='tt-key').text.strip()
            service = Service.objects.update_or_create(service_code='gg-{}'.format(line_name), defaults={
                'date': today,
                'line_name': line_name,
                'description': li.find(class_='tt-text').text.strip(),
                'region': region,
                'mode': 'bus',
                'operator': [operator],
            })[0]
            self.import_route_stops(session, service)
            sleep(1)

    def import_route_stops(self, session, service):
        res = session.get('http://m.buses.gg/index.php?content=Timetables&show_route=' + service.line_name + '&short')
        soup = BeautifulSoup(res.text, 'lxml')
        for table in soup.find_all('table', class_='headers'):
            i = 0
            for tr in table.find_all('tr'):
                stop_code = BeautifulSoup(tr.th.previous_element.previous_element, 'lxml').text.strip()
                atco_code = 'gg-{}'.format(stop_code)
                if not StopPoint.objects.filter(atco_code=atco_code).exists():
                    defaults = {
                        'naptan_code': stop_code,
                        'locality_centre': False,
                        'active': True,
                    }
                    defaults['common_name'] = tr.th.text.strip()
                    if ' - ' in defaults['common_name']:
                        defaults['common_name'], defaults['indicator'] = defaults['common_name'].split(' - ')
                    doppelganger = StopPoint.objects.filter(
                        atco_code__startswith='gg-',
                        common_name__iexact=defaults['common_name'],
                        latlong__isnull=False
                    ).first()
                    if doppelganger:
                        defaults['latlong'] = doppelganger.latlong
                    else:
                        print(tr)
                    StopPoint.objects.create(atco_code=atco_code, **defaults)
                StopUsage.objects.update_or_create(
                    order=i,
                    direction=tr.td.get('class')[0].lower(),
                    stop_id=atco_code,
                    service=service
                )
                i += 1

    def handle(self, *args, **options):
        session = requests.Session()

        region = Region.objects.update_or_create(id='GG', defaults={'name': 'Guernsey'})[0]

        StopPoint.objects.all().delete()
        self.import_stops()
        self.import_routes(session, region)
