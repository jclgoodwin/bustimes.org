import os
import tempfile
from vcr import use_cassette
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
from busstops.models import Region, Operator, DataSource, OperatorCode
from ...models import Route


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@freeze_time('2020-05-01')
class ImportBusOpenDataTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ea = Region.objects.create(pk='EA', name='East Anglia')
        op = Operator.objects.create(id='LYNX', region=ea, name='Lynx')
        source = DataSource.objects.create(name='National Operator Codes')
        OperatorCode.objects.create(operator=op, source=source, code='LYNX')

    @freeze_time('2020-05-01')
    @use_cassette(os.path.join(FIXTURES_DIR, 'bod_lynx.yaml'))
    @override_settings(STAGECOACH_OPERATORS=(), FIRST_OPERATORS=(), BOD_OPERATORS=[
        ('LYNX', 'EA', {
            'CO': 'LYNX',
        }),
    ])
    def test_import_bod(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(DATA_DIR=directory):
                call_command('import_bod', '')
                call_command('import_bod', '')

        route = Route.objects.get()
        self.assertEqual(route.code, 'Lynx_Clenchwarton_54_20200330')

        response = self.client.get('/services/54-kings-lynn-the-walpoles-via-clenchwarton')

        self.assertContains(response, """
            <tr>
                <th>
                    <a href="/stops/2900W0321">Walpole St Peter Lion Store</a>
                </th>
                <td>12:19</td>
            </tr>""", html=True)

        self.assertContains(response, """<p class="credit">Timetable data from <a href="https://data.bus-data.dft.gov.uk/category/dataset/35/">Lynx/\
Bus Open Data Service</a>, 1 April 2020</p>""")
