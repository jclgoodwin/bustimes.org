import os
from vcr import use_cassette
from django.test import TestCase
# from django.contrib.gis.geos import Point
from django.conf import settings
from django.core.management import call_command
from busstops.models import Region, Operator, Service
from .models import Situation


class SiriSXTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='NW', name='North West')
        operator = Operator.objects.create(region=region, id='HATT', name='Hattons of Huyton')
        service = Service.objects.create(line_name='156', service_code='156', date='2020-01-01', current=True)
        service.operator.add(operator)

    def test_siri_sx(self):
        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml'), match_on=['body']):
            call_command('import_siri_sx', 'hen hom', 'roger poultry')

        situation = Situation.objects.first()

        self.assertEqual(situation.situation_number, 'RGlzcnVwdGlvbk5vZGU6MTA3NjM=')
        self.assertEqual(situation.reason, 'roadworks')
        self.assertEqual(situation.summary, 'East Didsbury bus service changes Monday 11th May until Thursday 14th \
May. ')
        self.assertEqual(situation.text, 'Due to resurfacing works there will be bus service diversions and bus stop \
closures from Monday 11th May until Thursday 14th may. ')
        self.assertEqual(situation.reason, 'roadworks')

        response = self.client.get(situation.get_absolute_url())
        self.assertContains(response, '2020-05-10T23:01:00Z')

        consequence = situation.consequence_set.get()
        self.assertEqual(consequence.text, """Towards East Didsbury terminus customers should alight opposite East \
Didsbury Rail Station as this will be the last stop. From here its a short walk to the terminus. \n
Towards Manchester the 142 service will begin outside Didsbury Cricket club . """)

        with self.assertNumQueries(9):
            response = self.client.get('/services/156')
        self.assertContains(response, "<p>East Lancashire Road will be subjected to restrictions, at Liverpool Road,\
 from Monday 17 February 2020 for approximately 7 months.</p>")
        self.assertContains(response, "<p>Route 156 will travel as normal from St Helens to Haydock Lane, then u-turn \
at Moore Park Way roundabout, Haydock Lane, Millfield Lane, Tithebarn Road, then as normal route to Garswood (omitting \
East Lancashire Road and Liverpool Road).</p>""")
