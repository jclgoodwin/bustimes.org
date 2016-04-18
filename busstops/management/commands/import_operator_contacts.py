"""
Usage:

    ./manage.py import_operators_contacts
"""

import requests
from bs4 import BeautifulSoup
from time import sleep
from django.core.management.base import BaseCommand
from busstops.models import Operator


class Command(BaseCommand):
    @staticmethod
    def do_operator(operator):
        url = 'http://www.travelinesoutheast.org.uk/se/XSLT_REQUEST'
        request = requests.get(url, {
            'language': 'en',
            'itdLPxx_command': 'showOperatorInfo',
            'itdLPxx_opCode': operator.id,
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
            print operator
            print details
            operator.address = details.get('Address:') or ''
            operator.url = details.get('Website:') or ''
            operator.email = details.get('Email:') or ''
            operator.phone = details.get('Phone:') or ''
            operator.save()


    def handle(self, *args, **options):
        for operator in Operator.objects.filter(address=''):
            self.do_operator(operator)
            sleep(1)