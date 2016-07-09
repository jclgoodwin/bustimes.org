"""
Usage:

    ./manage.py import_operator_contacts < nocrecords.xml
"""

import sys
from bs4 import BeautifulSoup
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
        soup = BeautifulSoup(self.input, 'html.parser')

        noc_codes = {
            record.pubnmid.string: record.noccode.string
            for record in soup.noctable.find_all('noctablerecord')
        }

        for public_name in soup.publicname.find_all('publicnamerecord'):
            noc_code = noc_codes.get(public_name.pubnmid.string)

            operator = Operator.objects.filter(pk=noc_code.replace('=', '')).first()
            if not operator:
                break

            website = public_name.website.string
            address = public_name.complenq.string
            email = public_name.ttrteenq.string
            phone = public_name.fareenq.string

            if website or address or email or phone:
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
                try:
                    operator.save()
                except Exception as e:
                    print e, operator
