"""
Usage:

    ./manage.py import_operators < NOC_db.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Operator, Region


class Command(ImportFromCSVCommand):

    @staticmethod
    def get_region(region_id):
        if region_id in ('ADMIN', 'Admin', ''):
            region_id = 'GB'
        elif region_id in ('SC', 'YO', 'WA', 'LO'):
            region_id = region_id[0]

        return Region.objects.get(id=region_id)

    @classmethod
    def handle_row(cls, row):
        "Given a CSV row (a list), returns an Operator object"
        operator_id = row['NOCCODE'].replace('=', '')

        if operator_id == 'TVSR':
            return None

        region = cls.get_region(row['TLRegOwn'])

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
                region=region,
            )
        )
        return operator
