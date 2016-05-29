"""
Usage:

    ./manage.py import_scotch_operator_contacts < NOC_DB.csv
"""

import requests
from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Operator


class Command(ImportFromCSVCommand):

    scotch_operators = {
        operator['code']: operator
        for operator in requests.get('http://www.travelinescotland.com/lts/operatorList').json()['body']
    }

    @classmethod
    def handle_row(cls, row):
        operator = Operator.objects.filter(pk=row['NOCCODE']).first()

        if not operator:
            return

        if row['SC']:
            scotch = cls.scotch_operators.get(row['SC'])
            if scotch:
                operator.name = scotch['name']
                operator.address = scotch['address']
                operator.url = scotch['url']
                operator.email = scotch['email']
                operator.phone = scotch['phone']
                operator.save()
        else:
            cls.do_operator(operator, row)
