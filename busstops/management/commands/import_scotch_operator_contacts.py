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
            if scotch and len(row['NOCCODE']) == 4:
                operator = Operator.objects.filter(pk=row['NOCCODE']).first()
                if operator:
                    for key in ('name', 'address', 'url', 'email', 'phone'):
                        if scotch[key]:
                            setattr(operator, key, scotch[key])
                    operator.save()

    @staticmethod
    def process_rows(rows):
        return sorted(rows, reverse=True,
                      key=lambda r: (r['Duplicate'] != 'OK', r['Date Ceased']))
