import os
from vcr import use_cassette
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
from busstops.models import Region, Operator


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(STAGECOACH_OPERATORS=(), FIRST_OPERATORS=(), BOD_OPERATORS=[
    ('LYNX', 'EA', {
        'CO': 'LYNX',
    }),
])
class ImportBusOpenDataTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ea = Region.objects.create(pk='EA', name='East Anglia')
        Operator.objects.create(id='CO', region=ea, name='Lynx')

    @freeze_time('2020-05-01')
    @use_cassette(os.path.join(FIXTURES_DIR, 'bod_lynx.yaml'))
    def test_import(self):

        call_command('import_bod', '')
        call_command('import_bod', '')

        response = self.client.get('/services/54-kings-lynn-the-walpoles-via-clenchwarton')

        self.assertContains(response, """
            <tr>
                <th>
                    <a href="/stops/2900W0321">Walpole St Peter Lion Store</a>
                </th>
                <td>12:19</td>
            </tr>""", html=True)
