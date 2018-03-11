import os
import json
import requests
from django.conf import settings
from django.core.management.base import BaseCommand


JSON_NAME = 'NPTGLastSubs_Load.ashx'


class Command(BaseCommand):
    @staticmethod
    def get_old_rows():
        try:
            with open(os.path.join(settings.DATA_DIR, 'NaPTAN', JSON_NAME)) as old_file:
                old_json = json.load(old_file)
        except IOError:
            return
        return old_json.get('rows')

    @staticmethod
    def get_diff(new_rows, old_rows):
        changed_regions = []
        changed_areas = []

        for i, row in enumerate(new_rows):
            cells = row.get('cell')[:-1]
            if old_rows:
                old_cells = old_rows[i].get('cell')[:-1]

            if not old_rows or cells != old_cells:
                if cells[0] not in changed_regions:
                    changed_regions.append(cells[0])
                changed_areas.append(cells[2])

        return (changed_regions, changed_areas)

    @staticmethod
    def get_data(areas=None):
        params = {
            'format': 'csv'
        }
        if areas:
            params['LA'] = '|'.join(areas)
        return requests.get('http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx', params, stream=True)

    def handle(self, *args, **options):
        new_response = requests.get('http://naptan.app.dft.gov.uk/GridMethods/%s' % JSON_NAME)
        new_rows = [row for row in new_response.json()['rows'] if row['cell'][0]]
        old_rows = [row for row in self.get_old_rows() if row['cell'][0]]

        changed_regions, changed_areas = self.get_diff(new_rows, old_rows)

        if changed_areas:
            print(changed_regions, changed_areas)

            response = self.get_data(changed_areas)

            if response.headers.get('Content-Type') != 'application/zip':
                print(response)
                print(response.url)
                print(response.content)
                print(response.headers)
                response = self.get_data()

            with open(os.path.join(settings.DATA_DIR, 'NaPTAN', 'naptan.zip'), 'wb') as zip_file:
                for chunk in response.iter_content(chunk_size=102400):
                    zip_file.write(chunk)

            with open(os.path.join(settings.DATA_DIR, 'NaPTAN', JSON_NAME), 'w') as json_file:
                json_file.write(new_response.text)
