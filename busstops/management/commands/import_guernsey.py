import os
import json
import requests
from time import sleep
from datetime import date
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.gis.geos import Point, LineString, MultiLineString
from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import Region, StopPoint, Service, StopUsage, Operator


def import_stops(region):
    with open(os.path.join(settings.DATA_DIR, '{}.json'.format(region.name.lower()))) as open_file:
        records = json.load(open_file)
    for zoom_level in records:
        for place in zoom_level['places']:
            assert place['icon'] == ['stop', 'flag-shadow']
            name, stop_code = place['name'].split('\n')
            assert stop_code.startswith('Bus stop code - ')
            _, stop_code = stop_code.split(' - ')
            if not stop_code:
                continue
            stop_code = int(stop_code)
            defaults = {
                'common_name': name,
                'naptan_code': stop_code,
                'latlong': Point(*place['posn'][::-1]),
                'locality_centre': False,
                'active': True,
            }
            if ', ' in name:
                defaults['common_name'], defaults['indicator'] = name.split(', ')
                if defaults['indicator'].endswith('bound'):
                    defaults['bearing'] = defaults['indicator'][0]
                    defaults['indicator'] = defaults['bearing'] + '-bound'
            elif region.name == 'Jersey' and defaults['common_name'].lower().startswith('stand '):
                defaults['indicator'] = 'Stand ' + defaults['common_name'][-1]
                defaults['common_name'] = 'Liberation Station'
            elif defaults['common_name'][-2:] in {' N', ' E', ' S', ' W'}:
                defaults['bearing'] = defaults['common_name'][-1]
                defaults['indicator'] = defaults['bearing'] + '-bound'
                defaults['common_name'] = defaults['common_name'][:-2]
            StopPoint.objects.update_or_create(defaults, atco_code='{}-{}'.format(region.id.lower(), stop_code))


def import_routes(region, operator, url, session):
    today = date.today()
    res = session.get(url)
    soup = BeautifulSoup(res.text, 'lxml')
    for li in soup.find(id='main-timetable-list').find_all('li'):
        line_name = li.find(class_='tt-key').text.strip()
        slug = li.find('a')['href'].split('/')[-2]
        service_code = '{}-{}'.format(region.id.lower(), line_name.upper())
        service = Service.objects.update_or_create(service_code=service_code, defaults={
            'date': today,
            'line_name': line_name,
            'description': li.find(class_='tt-text').text.strip(),
            'region': region,
            'mode': 'bus',
            'current': True
        })[0]
        service.operator.set([operator])
        import_route_stops(region, service, slug, url, session)
        if region.id == 'GG':
            import_kml(service, session)
        sleep(1)


def import_route_stops(region, service, slug, url, session):
    StopUsage.objects.filter(service=service).delete()
    res = session.get('{}/{}/FALSE'.format(url, slug))
    soup = BeautifulSoup(res.text, 'lxml')
    for table in soup.find_all('table', class_='headers'):
        i = 0
        for tr in table.find_all('tr'):
            stop_code = int(BeautifulSoup(tr.th.previous_element.previous_element, 'lxml').text.strip())
            atco_code = '{}-{}'.format(region.id.lower(), stop_code)
            if not StopPoint.objects.filter(atco_code=atco_code).exists():
                defaults = {
                    'naptan_code': stop_code,
                    'locality_centre': False,
                    'active': True,
                }
                defaults['common_name'] = tr.th.text.strip()
                if ' - ' in defaults['common_name']:
                    defaults['common_name'], defaults['indicator'] = defaults['common_name'].split(' - ')
                    if defaults['indicator'].endswith('bound'):
                        defaults['bearing'] = defaults['indicator'][0]
                        defaults['indicator'] = defaults['bearing'] + '-bound'
                elif defaults['common_name'][-2:] in {' N', ' E', ' S', ' W'}:
                    defaults['bearing'] = defaults['common_name'][-1]
                    defaults['indicator'] = defaults['bearing'] + '-bound'
                    defaults['common_name'] = defaults['common_name'][:-2]
                doppelganger = StopPoint.objects.filter(
                    atco_code__startswith=region.id.lower() + '-',
                    common_name__iexact=defaults['common_name'],
                    latlong__isnull=False
                ).first()
                if doppelganger:
                    defaults['latlong'] = doppelganger.latlong
                StopPoint.objects.create(atco_code=atco_code, **defaults)
            StopUsage.objects.update_or_create(
                {
                    'order': i,
                    'timing_status': 'OTH'
                },
                direction=tr.td.get('class')[0].lower(),
                stop_id=atco_code,
                service=service
            )
            i += 1
    # mark major stops as major
    res = session.get('{}/{}/TRUE'.format(url, slug))
    soup = BeautifulSoup(res.text, 'lxml')
    stop_ids = set()
    for table in soup.find_all('table', class_='headers'):
        i = 0
        for tr in table.find_all('tr'):
            stop_code = int(BeautifulSoup(tr.th.previous_element.previous_element, 'lxml').text.strip())
            stop_ids.add('{}-{}'.format(region.id.lower(), stop_code))
    StopUsage.objects.filter(service=service, stop_id__in=stop_ids).update(timing_status='PTP')


def import_kml(service, session):
    res = session.get('http://buses.gg/kmls/' + service.line_name + '.kml')
    kml = BeautifulSoup(res.text, 'lxml')
    line_strings = []
    for line_string in kml.find_all('linestring'):
        points = [point.split(',') for point in line_string.find('coordinates').text.split()]
        line_strings.append(LineString(*[Point(float(point[0]), float(point[1])) for point in points]))
    service.geometry = MultiLineString(*line_strings)
    service.save()


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        region = Region.objects.update_or_create(id='GG', defaults={'name': 'Guernsey'})[0]
        operator = Operator.objects.update_or_create(id='guernsey', name='Guernsey Buses', region=region)[0]

        session = requests.Session()

        import_stops(region)

        Service.objects.filter(region=region).update(current=False)

        import_routes(region, operator, 'http://buses.gg/routes_and_times/timetables', session)

        StopPoint.objects.filter(atco_code__startswith='gg-').exclude(service__current=True).delete()
