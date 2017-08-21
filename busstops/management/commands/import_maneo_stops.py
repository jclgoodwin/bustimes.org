"""Usage:

    ./manage.py import_maneo_stops < Manéo\ Points\ d\'arrêt\ des\ lignes\ régulières.csv
"""
import requests
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
from bs4 import BeautifulSoup
from titlecase import titlecase
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint, Service, StopUsage


session = requests.Session()


class Command(ImportFromCSVCommand):
    encoding = 'utf-8-sig'

    def handle_row(self, row):
        atco_code = 'maneo-' + row['CODE']
        defaults = {
            'locality_centre': False,
            'active': True,
            'latlong': row['geometry']
        }

        name = row['\ufeffAPPCOM']
        name_parts = name.split(' - ', 1)
        if len(name_parts) == 2:
            if name_parts[1].startswith('Desserte'):
                name = name_parts[0]
                defaults['indicator'] = name_parts[1]
            else:
                defaults['town'] = titlecase(name_parts[1])

        defaults['common_name'] = titlecase(name)

        stop = StopPoint.objects.update_or_create(atco_code=atco_code, defaults=defaults)[0]

        url = 'http://www.commentjyvais.fr/en/schedule/result/?' + urlencode({
            'schedule[stop_area][autocomplete-hidden]': 'stop_area:G50:SA:' + row['IDARRET']
        })
        res = session.get(url)
        soup = BeautifulSoup(res.text, 'lxml')

        lines = {line.text.strip() for line in soup.find_all('span', {'class': 'ctp-line-code'})}

        for line in lines:
            if len(line) > 24:
                continue
            service = Service.objects.update_or_create(
                service_code='maneo-' + line,
                line_name=line,
                region_id='FR',
                date='2017-01-01'
            )[0]
            StopUsage.objects.update_or_create(service=service, stop=stop, defaults={
                'order': 0
            })
