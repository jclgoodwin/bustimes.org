import os
import xmltodict
from django.core.management.base import BaseCommand


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Command(BaseCommand):
    def handle(self, **kwargs):
        path = 'connexions_Harrogate_Coa_16.286Z_IOpbaMX.xml'
        path = os.path.join(BASE_DIR, path)

        print(path)
        with open(path, 'rb') as open_file:
            # print(open_file)
            data = xmltodict.parse(open_file)
            for frame in data['PublicationDelivery']['dataObjects']['CompositeFrame']:
                print(dict(frame))
