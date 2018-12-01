# -*- coding: utf-8 -*-
"""Usage:

   ./manage.py import_maneo_stops < "Manéo Points d'arrêt des lignes régulières.csv"
"""
import requests
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from titlecase import titlecase
from django.utils.text import slugify
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint, Operator, Service, StopUsage


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

        name = row.get('\ufeffAPPCOM', row.get('APPCOM'))
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

        line_elements = soup.find_all('div', {'class': 'line-info'})
        lines = set()
        for element in line_elements:
            line = element.find('span', {'class': 'ctp-line-code'})
            if line is None:
                continue
            line = line.text.strip()
            if line in lines:
                continue
            lines.add(line)
            if len(line) > 24:
                print(line)
                continue

            operator_name = element.find('img')['alt'].split()[0]
            operator = Operator.objects.update_or_create(
                id=slugify(operator_name).upper(),
                name=operator_name,
                region_id='FR'
            )[0]

            service = Service.objects.update_or_create(
                service_code='maneo-' + line,
                line_name=line,
                region_id='FR',
                date='2017-01-01'
            )[0]

            service.operator.add(operator)

            StopUsage.objects.update_or_create(service=service, stop=stop, defaults={
                'order': 0
            })
