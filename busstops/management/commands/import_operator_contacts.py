"""
Usage:

    ./manage.py import_operator_contacts < NOC_DB.csv
"""

import requests
from bs4 import BeautifulSoup
from time import sleep
from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Operator


REGIONS = ('LO','SW','WM','WA','YO','NW','NE','SC','SE','EA','EM','NI','NX','Megabus','New Bharat','Terravision','NCSD')


class Command(ImportFromCSVCommand):

    scotch_operators = {
        operator['code']: operator
        for operator in requests.get('http://www.travelinescotland.com/lts/operatorList').json()['body']
    }

    @staticmethod
    def do_operator(operator, row):

        print {
            key: row[key] for key in ('LO','SW','WM','WA','YO','NW','NE','SC','SE','EA','EM','NI','NX','Megabus','New Bharat','Terravision','NCSD')
        }
        local_code = row['SW'] or row['EA'] or row['SE'] or row['EM'] or row['WM']
        return
        if not local_code:
            return

        url = 'http://www.travelinesoutheast.org.uk/se/XSLT_REQUEST'
        request = requests.get(url, {
            'language': 'en',
            'itdLPxx_command': 'showOperatorInfo',
            'itdLPxx_opCode': local_code,
            'itdLPxx_opName': operator.name
        })
        soup = BeautifulSoup(request.text, 'html.parser')
        main = soup.findAll('div', {'class': 'main'})[1]
        if main.text.strip() != 'Sorry - we don\'t have contact details for this organisation':
            details = {}
            for row in main.table.findAll('tr'):
                cells = row.findAll('td')
                field_name = cells[0].text.strip() or field_name
                field_value = cells[-1].text.strip()
                if field_name in details:
                    details[field_name] += '\n' + field_value
                else:
                    details[field_name] = field_value
            # print operator
            # print details
            operator.address = details.get('Address:') or ''
            operator.url = details.get('Website:') or ''
            operator.email = details.get('Email:') or ''
            operator.phone = details.get('Phone:') or ''
            operator.save()
        else:
            print request.url, main

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
