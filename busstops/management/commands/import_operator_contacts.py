"""
Usage:

    ./manage.py import_operator_contacts < nocrecords.xml
"""
import warnings
from io import open
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from ...models import Operator
from ...views import FIRST_OPERATORS


class Command(BaseCommand):
    input = 0

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
        with open(self.input, encoding='cp1252') as input:
            soup = BeautifulSoup(input, 'html.parser')

        noc_codes = {
            record.pubnmid.string: record.noccode.string
            for record in soup.noctable.find_all('noctablerecord')
        }

        for public_name in soup.publicname.find_all('publicnamerecord'):
            noc_code = noc_codes.get(public_name.pubnmid.string)

            if not noc_code or len(noc_code) < 4:
                continue

            try:
                operator = Operator.objects.get(pk=noc_code.replace('=', ''))
            except Operator.DoesNotExist as e:
                warnings.warn('{} {}'.format(e, noc_code))
                continue

            if noc_code in FIRST_OPERATORS:
                operator.url = 'https://www.firstgroup.com/%s' % FIRST_OPERATORS[noc_code]
                operator.email = ''
                operator.phone = ''
                operator.save()
                continue

            website = public_name.website.string
            address = public_name.complenq.string
            email = public_name.ttrteenq.string
            phone = public_name.fareenq.string

            if website or address or email or phone:
                if website:
                    website = website.split('#')[-2]
                    if '.' in website and 'mailto:' not in website and ' ' not in website:
                        if website.startswith('http'):
                            operator.url = website
                        else:
                            operator.url = 'http://' + website
                if address and len(address) <= 128 and ', ' in address:
                    operator.address = self.format_address(address)
                if email and '@' in email and ' ' not in email.strip():
                    operator.email = email.strip()
                if phone and len(phone) <= 128:
                    operator.phone = phone

                try:
                    operator.save()
                except ValidationError as errors:
                    errors = dict(errors)
                    if 'email' in errors:
                        operator.email = ''
                    if 'url' in errors:
                        operator.url = ''
                    operator.save()
