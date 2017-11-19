"""
https://www.transportforireland.ie/transitData/TransX_2015-01-21T14-03-54_WEXFORDBUS.xml
"""

import xml.etree.cElementTree as ET
from django.core.management.base import BaseCommand
from ...models import Locality


class Command(BaseCommand):
    ns = {'txc': 'http://www.transxchange.org.uk/'}

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('filenames', nargs='+', type=str)

    def handle_file(self, filename):
        iterator = ET.iterparse(filename)
        for _, element in iterator:
            tag = element.tag[33:]
            if tag == 'AnnotatedNptgLocalityRef':
                locality_id = element.find('txc:NptgLocalityRef', self.ns).text
                locality_name = element.find('txc:LocalityName', self.ns).text
                locality = Locality.objects.filter(id=locality_id)
                if locality.exists():
                    locality.update(name=locality_name)
                    print(locality_name)
                else:
                    print(locality_id, locality_name)

    def handle(self, *args, **options):
        for filename in options['filenames']:
            self.handle_file(filename)
