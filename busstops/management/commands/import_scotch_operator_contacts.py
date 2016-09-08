"""
Usage:

    ./manage.py import_scotch_operator_contacts < NOC_DB.csv
"""

import requests
from ..import_from_csv import ImportFromCSVCommand
from ...models import Operator


class Command(ImportFromCSVCommand):
    scotch_operators = {
        operator['code']: operator
        for operator in requests.get('http://www.travelinescotland.com/lts/operatorList').json()['body']
    }

    @classmethod
    def handle_row(cls, row):
        if row['SC']:
            scotch = cls.scotch_operators.get(row['SC'])

            if scotch:
                Operator.objects.filter(pk=row['NOCCODE']).update(
                    name=scotch['name'],
                    address=scotch['address'],
                    url=scotch['url'],
                    email=scotch['email'],
                    phone=scotch['phone']
                )

    @staticmethod
    def process_rows(rows):
        return sorted(rows, reverse=True,
                      key=lambda r: (r['Duplicate'] != 'OK', r['Date Ceased']))
