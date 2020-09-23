import os
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from busstops.models import DataSource


class Command(BaseCommand):
    url = 'http://naptan.app.dft.gov.uk'

    def get_data(self, areas=None):
        params = {
            'format': 'csv'
        }
        if areas:
            params['LA'] = '|'.join(areas)
        return requests.get(f'{self.url}/DataRequest/Naptan.ashx', params, stream=True, timeout=60)

    def handle(self, *args, **options):
        source, created = DataSource.objects.get_or_create(name='NaPTAN')

        response = requests.get('http://naptan.app.dft.gov.uk/GridMethods/NPTGLastSubs_Load.ashx', timeout=10)
        new_rows = response.json()
        old_rows = source.settings

        if old_rows:
            changes = [new_row['DataBaseID'] for i, new_row in enumerate(new_rows) if old_rows[i] != new_row]

            if not changes:
                return

            response = self.get_data(changes)  # get data for changed areas only

            if response.headers.get('Content-Type') != 'application/zip':
                print(response.content.decode())
                response = self.get_data()
        else:  # get all data
            response = self.get_data()

        with open(os.path.join(settings.DATA_DIR, 'NaPTAN', 'naptan.zip'), 'wb') as zip_file:
            for chunk in response.iter_content(chunk_size=102400):
                zip_file.write(chunk)

        source.settings = new_rows
        source.save(update_fields=['settings'])
