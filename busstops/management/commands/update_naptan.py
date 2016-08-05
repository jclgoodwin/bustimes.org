
import json
import requests

from django.core.management.base import BaseCommand


JSON_NAME = 'NPTGLastSubs_Load.ashx'


class Command(BaseCommand):
    @staticmethod
    def get_old_rows():
        try:
            with open(JSON_NAME) as old_file:
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

    def handle(self, *args, **options):
        new_response = requests.get('http://naptan.app.dft.gov.uk/GridMethods/%s' % JSON_NAME)
        new_rows = new_response.json().get('rows')
        old_rows = self.get_old_rows()

        changed_regions, changed_areas = self.get_diff(new_rows, old_rows)

        if changed_areas:
            print(changed_regions, changed_areas)
            response = requests.get(
                'http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx',
                {
                    'format': 'csv',
                    'LA': '|'.join(changed_areas)
                },
                stream=True
            )

            with open('naptan.zip', 'wb') as new_file:
                for chunk in response.iter_content(chunk_size=1024):
                    new_file.write(chunk)

            with open(JSON_NAME, 'w') as new_file:
                new_file.write(new_response.text)
