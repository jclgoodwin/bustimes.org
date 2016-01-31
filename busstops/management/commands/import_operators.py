"""
Usage:

    ./manage.py import_operators < NOC_db.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Operator


class Command(ImportFromCSVCommand):

    @staticmethod
    def get_region_id(region_id):
        if region_id in ('ADMIN', 'Admin', ''):
            return 'GB'
        elif region_id in ('SC', 'YO', 'WA', 'LO'):
            return region_id[0]

        return region_id

    @classmethod
    def handle_row(cls, row):
        "Given a CSV row (a list), returns an Operator object"
        if row['Duplicate'] != 'OK' and row['NOCCODE'] != 'FCYM': # First Cymru is marked as a duplicate even though it isn't
            return None

        operator_id = row['NOCCODE'].replace('=', '')

        if operator_id == 'TVSR':
            return None

        if row['OperatorPublicName'] in ('First', 'Arriva', 'Stagecoach') \
            or row['OperatorPublicName'].startswith('inc.') \
            or row['OperatorPublicName'].startswith('formerly'):
            name = row['RefNm']
        elif row['OperatorPublicName'] != '':
            name = row['OperatorPublicName']
        else:
            name = row['OpNm']

        name = name.replace('\'', u'\u2019') # Fancy apostrophe

        operator = Operator.objects.update_or_create(
            id=operator_id,
            defaults=dict(
                name=name.strip(),
                vehicle_mode=row['Mode'].lower().replace('ct operator', 'community transport').replace('drt', 'demand responsive transport'),
                region_id=cls.get_region_id(row['TLRegOwn']),
            )
        )
        return operator
