"""
Usage:

    ./manage.py import_operators < NOC_db.csv
"""

from django.utils import timezone
from ..import_from_csv import ImportFromCSVCommand
from ...models import Operator, OperatorCode, DataSource


class Command(ImportFromCSVCommand):
    code_sources = {
        'NOCCODE': 'National Operator Codes',
        'Licence': 'Licence',
        'LO': 'L',
        'SW': 'SW',
        'WM': 'WM',
        'WA': 'W',
        'YO': 'Y',
        'NW': 'NW',
        'NE': 'NE',
        'SC': 'S',
        'SE': 'SE',
        'EA': 'EA',
        'EM': 'EM',
    }
    removed_operator_ids = {'EAST', 'AW'}  # Eastons Coaches and Arriva Trains Wales clash with some Irish operators

    @staticmethod
    def get_region_id(region_id):
        if region_id in {'ADMIN', 'Admin', 'Taxi', ''}:
            return 'GB'
        elif region_id in {'SC', 'YO', 'WA', 'LO'}:
            return region_id[0]

        return region_id

    @staticmethod
    def is_rubbish_name(name):
        """Given an OperatorPublicName, return True if it should be
        ignored in favour of the RefNm or OpNm fields
        """
        return (
            name in {'First', 'Arriva', 'Stagecoach', 'Oakwood Travel', 'Arriva North West'} or
            name.startswith('inc.') or
            name.startswith('formerly') or
            name.isupper()
        )

    @classmethod
    def get_name(cls, row):
        """Given a row dictionary, returns the best-seeming name string"""
        if cls.is_rubbish_name(row['OperatorPublicName']):
            if row['RefNm'] != '':
                return row['RefNm']
            return row['OpNm']
        if row['OperatorPublicName'] != '':
            return row['OperatorPublicName']
        return row['OpNm']

    def handle_row(self, row):
        """Given a CSV row (a list), returns an Operator object"""

        operator_id = row['NOCCODE'].replace('=', '')
        if operator_id in self.removed_operator_ids:
            return
        operator_name = self.get_name(row).replace('\'', '\u2019').strip()  # Fancy apostrophe
        region_id = self.get_region_id(row['TLRegOwn'])

        mode = row['Mode'].lower()
        if mode == 'airline':
            return
        if mode == 'ct operator':
            mode = 'community transport'
        elif mode == 'drt':
            mode = 'demand responsive transport'

        defaults = {
            'name': operator_name,
            'vehicle_mode': mode,
            'region_id': region_id
        }

        operator = Operator.objects.update_or_create(
            id=operator_id,
            defaults=defaults
        )[0]
        for key in self.code_sources:
            if row[key]:
                OperatorCode.objects.update_or_create(code=row[key].replace('=', ''), source=self.code_sources[key],
                                                      defaults={'operator': operator})

    def handle(self, *args, **options):
        # Operator.objects.filter(id__in=self.removed_operator_ids).delete()
        for key in self.code_sources:
            self.code_sources[key] = DataSource.objects.get_or_create(name=self.code_sources[key], defaults={
                'datetime': timezone.now()
            })[0]
        return super().handle(*args, **options)
