"""
Usage:

    ./manage.py import_operators < NOC_db.csv
"""

import requests
from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Operator


class Command(ImportFromCSVCommand):

    scotch_operators = {
        operator['code']: operator
        for operator in requests.get('http://www.travelinescotland.com/lts/operatorList').json()['body']
    }

    @staticmethod
    def get_region_id(region_id):
        if region_id in ('ADMIN', 'Admin', ''):
            return 'GB'
        elif region_id in ('SC', 'YO', 'WA', 'LO'):
            return region_id[0]

        return region_id

    @staticmethod
    def get_name(row):
        if row['OperatorPublicName'] in ('First', 'Arriva', 'Stagecoach') \
            or row['OperatorPublicName'].startswith('inc.') \
            or row['OperatorPublicName'].startswith('formerly'):
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

        name = cls.get_name(row).replace('\'', u'\u2019') # Fancy apostrophe
        defaults = {
            'name': name.strip(),
            'vehicle_mode': row['Mode'].lower().replace('ct operator', 'community transport').replace('drt', 'demand responsive transport'),
            'region_id': cls.get_region_id(row['TLRegOwn']),
        }

        if row['SC']:
            scotch = cls.scotch_operators.get(row['SC'])
            if scotch:
                defaults['name'] = scotch['name']
                defaults['address'] = scotch['address']
                defaults['url'] = scotch['url']
                defaults['email'] = scotch['email']
                defaults['phone'] = scotch['phone']

        operator = Operator.objects.update_or_create(
            id=operator_id,
            defaults=defaults
        )
        return operator
