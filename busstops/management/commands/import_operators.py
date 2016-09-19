"""
Usage:

    ./manage.py import_operators < NOC_db.csv
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import Operator


class Command(ImportFromCSVCommand):
    @staticmethod
    def get_region_id(region_id):
        if region_id in ('ADMIN', 'Admin', 'Taxi', ''):
            return 'GB'
        elif region_id in ('SC', 'YO', 'WA', 'LO'):
            return region_id[0]

        return region_id

    @staticmethod
    def is_rubbish_name(name):
        return (
            name in ('First', 'Arriva', 'Stagecoach') or
            name.startswith('inc.') or
            name.startswith('formerly') or
            name == 'OWENS OF OSWESTRY COACHES LTD'
        )

    @classmethod
    def get_name(cls, row):
        if cls.is_rubbish_name(row['OperatorPublicName']):
            if row['RefNm'] != '':
                return row['RefNm']
            return row['OpNm']
        if row['OperatorPublicName'] != '':
            return row['OperatorPublicName']
        return row['OpNm']

    @classmethod
    def handle_row(cls, row):
        "Given a CSV row (a list), returns an Operator object"

        operator_id = row['NOCCODE'].replace('=', '')
        if operator_id in ('TVSR', 'HBSY') or (operator_id == 'FMAN' and row['Duplicate'] != 'OK'):
            return None

        name = cls.get_name(row).replace('\'', '\u2019')  # Fancy apostrophe

        mode = row['Mode'].lower()
        if mode == 'ct operator':
            mode = 'community transport'
        elif mode == 'drt':
            mode = 'demand responsive transport'

        defaults = {
            'name': name.strip(),
            'vehicle_mode': mode,
            'region_id': cls.get_region_id(row['TLRegOwn']),
        }

        operator = Operator.objects.update_or_create(
            id=operator_id,
            defaults=defaults
        )
        return operator
