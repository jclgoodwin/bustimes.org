"""https://data.dublinked.ie/dataset/nptg
"""

import xml.etree.cElementTree as ET
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from ...models import Region, AdminArea, Locality


class Command(BaseCommand):
    ns = {'nptg': 'http://www.naptan.org.uk/'}

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('filenames', nargs='+', type=str)

    def handle_region(self, element):
        self.region = self.regions[element.find('nptg:RegionCode', self.ns).text]

        for area in element.find('nptg:AdministrativeAreas', self.ns):
            self.handle_area(area)

    def handle_area(self, element):
        area = AdminArea(id=element.find('nptg:AdministrativeAreaCode', self.ns).text,
                         atco_code=element.find('nptg:AtcoAreaCode', self.ns).text,
                         name=element.find('nptg:Name', self.ns).text,
                         region=self.region)
        area.save()

    def handle_locality(self, element):
        location_element = element.find('nptg:Location/nptg:Translation', self.ns)
        latlong = Point(float(location_element.find('nptg:Longitude', self.ns).text),
                        float(location_element.find('nptg:Latitude', self.ns).text))
        Locality(
            id=element.find('nptg:NptgLocalityCode', self.ns).text,
            admin_area_id=element.find('nptg:AdministrativeAreaRef', self.ns).text,
            name=element.find('nptg:Descriptor/nptg:LocalityName', self.ns).text,
            latlong=latlong
        ).save()

    def handle(self, *args, **options):
        self.regions = {
            'CON': Region(id='CO', name='Connacht'),
            'LEI': Region(id='LE', name='Leinster'),
            'MUN': Region(id='MU', name='Munster'),
            'ULS': Region(id='UL', name='Ulster'),
            'ULS_NI': Region(id='NI', name='Northern Ireland')
        }
        for region in self.regions.values():
            region.save()

        for filename in options['filenames']:
            iterator = ET.iterparse(filename)
            for _, element in iterator:
                tag = element.tag[27:]
                if tag == 'Regions':
                    for region in element:
                        self.handle_region(region)
                    element.clear()
                elif tag == 'NptgLocality':
                    self.handle_locality(element)
                    element.clear()
