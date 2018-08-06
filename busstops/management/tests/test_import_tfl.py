import os
from vcr import use_cassette
from django.test import TestCase
from django.core.management import call_command
from ...models import Region, Service, StopPoint, StopUsage


class ImportTfLTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        london = Region.objects.create(id='L', name='London')
        cls.service = Service.objects.create(line_name='RV1', description='Covent Garden - Waterloo - Tower Gateway',
                                             date='2017-01-01', region=london, current=True, net='tfl')
        stop = StopPoint.objects.create(atco_code='490002076RV', locality_centre=False, active=True)
        StopUsage.objects.create(service=cls.service, stop=stop, order=1)

    def test_import_tfl(self):
        with use_cassette(os.path.join('data', 'vcr', 'import_tfl.yaml'), decode_compressed_response=True):
            call_command('import_tfl')

        self.assertEqual(self.service.get_traveline_link(),
                         ('https://tfl.gov.uk/bus/timetable/RV1/', 'Transport for London'))
