"""
Usage:

    ./manage.py import_operator_contacts < nocrecords.xml
"""

import xml.etree.cElementTree as ET
import sys
from django.core.management.base import BaseCommand
from ...models import Operator


class Command(BaseCommand):

    input = sys.stdin

    @classmethod
    def format_address(cls, address):
        address_parts = address.split(', ')
        address_last_line_parts = address_parts[-1].split(' ')
        if len(address_last_line_parts) > 2:
            pre_postcode = ' '.join(address_last_line_parts[:-2])
            postcode = ' '.join(address_last_line_parts[-2:])
            address_parts[-1] = pre_postcode + '\n' + postcode
        return '\n'.join(address_parts)

    def handle(self, *args, **options):
        root = ET.parse(self.input).getroot()
        noc_codes = {
            record.find('PubNmId').text: record.find('NOCCODE').text
            for record in root.find('NOCTable')
        }

        for public_name in root.find('PublicName'):
            noc_code = noc_codes.get(public_name.find('PubNmId').text)

            operator = Operator.objects.filter(pk=noc_code.replace('=', '')).first()
            if not operator:
                break

            website = public_name.find('Website').text
            address = public_name.find('ComplEnq').text
            email = public_name.find('TTRteEnq').text
            phone = public_name.find('FareEnq').text

            if website or address or email or tel:
                if website:
                    website = website.split('#')[-2]
                    if '.' in website and 'mailto:' not in website:
                        if operator:
                            operator.url = website
                if address and len(address) <= 128 and ', ' in address:
                    operator.address = self.format_address(address)
                if email:
                    operator.email = email
                if phone:
                    operator.phone = phone
                operator.save()
