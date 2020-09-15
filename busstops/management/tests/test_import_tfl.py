import os
from vcr import use_cassette
from django.test import TestCase
from django.core.management import call_command
from ...models import Region, Service, StopPoint, StopUsage, DataSource


class ImportTfLTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='L', name='London')
        source = DataSource.objects.create(name='L')
        cls.service = Service.objects.create(service_code='tfl_64-RV1-A-y05', line_name='RV1',
                                             description='Covent Garden - Waterloo - Tower Gateway',
                                             date='2017-01-01', region=region, source=source, current=True)
        stop = StopPoint.objects.create(atco_code='490002076RV', locality_centre=False, active=True)
        StopUsage.objects.create(service=cls.service, stop=stop, order=1)

    def test_import_tfl(self):
        self.assertEqual(list(self.service.get_traveline_links()), [])

        with use_cassette(os.path.join('data', 'vcr', 'import_tfl.yaml'), decode_compressed_response=True):
            call_command('import_tfl')

        self.assertEqual(list(self.service.get_traveline_links()),
                         [('https://tfl.gov.uk/bus/timetable/RV1/', 'Timetable on the Transport for London website')])
