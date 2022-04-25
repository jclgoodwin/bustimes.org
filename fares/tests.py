from pathlib import Path
from vcr import use_cassette
from django.test import TestCase
from django.core.management import call_command
from busstops.models import Operator, Service
from .management.commands.import_netex_fares import Command
from .models import Tariff, TimeInterval, DataSet, FareZone


class FaresTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a_c_williams = Operator.objects.create(id='WMSA')
        cls.wm06 = Service.objects.create(line_name='wm06', current=True)
        cls.wm06.operator.add(cls.a_c_williams)

    def test_bod_netex(self):
        path = Path(__file__).resolve().parent / 'data'

        with use_cassette(str(path / 'bod_fares.yaml')):
            with self.assertLogs('fares.management.commands.import_netex_fares') as cm:
                call_command('import_netex_fares', 'XCpEBAoqPDfVdYRoUahb3F2nEZTJJCULXZCPo5x8')

        self.assertEqual(cm.output, [
            'INFO:fares.management.commands.import_netex_fares:AC Williams_20201119 06:45:17',
            'WARNING:fares.management.commands.import_netex_fares:Service matching query does not exist. WMSA WM07',
            'INFO:fares.management.commands.import_netex_fares:AC Williams_20201119 06:46:57',
        ])

        tariff = Tariff.objects.get(name="A C Williams WM06 - single fares")

        self.assertEqual(self.wm06, tariff.services.get())

        # tariff detail view
        response = self.client.get(tariff.get_absolute_url())

        self.assertContains(response, "A C Williams WM06 - single fares")
        self.assertContains(response, "<td>£1.70</td>")
        self.assertContains(response, "RAF Cranwell")

        origin = FareZone.objects.get(name='Welbourn')
        destination = FareZone.objects.get(name='Cranwell')
        response = self.client.get(
            f'{tariff.get_absolute_url()}?origin={origin.id}&destination={destination.id}'
        )

        self.assertContains(response, "<h3>Welbourn to Cranwell</h3>")
        self.assertContains(response, "<p>adult single: £1.50</p>")

        # dataset detail view
        response = self.client.get(
            f'{tariff.source.get_absolute_url()}?origin={origin.id}&destination={destination.id}'
        )
        self.assertContains(response, "<h3>Welbourn to Cranwell</h3>")
        self.assertContains(response, "<p>adult single: £1.50</p>")

        # fares index
        # response = self.client.get('/fares/')
        # self.assertContains(response, '£1.40–£1.70')

        self.assertEqual(TimeInterval.objects.count(), 0)

    def test_ad_hoc(self):
        command = Command()
        command.user_profiles = {}
        command.sales_offer_packages = {}
        command.fare_products = {}

        source = DataSet.objects.create()

        base_path = Path(__file__).resolve().parent / 'data'

        for filename in (
            'connexions_Harrogate_Coa_16.286Z_IOpbaMX.xml',
            'FLDSa0eb4e10_1605250801329.xml',
            'KBUS_FF_ArrivaAdd-on_2Multi_6d7e341a-0680-4397-9b3f-90a290087494_637613495098903655.xml',
            'FECS_23A_Outbound_YPSingle_6764fa3b-4b05-4331-9bea-c7bb90212531_637829447220443476.xml',
            'LYNX 39 single.xml',
            'LYNX Coast.xml',
            'LYNX Townrider.xml',
            'NADS_103A_Inbound_AdultReturn_aae41d08-15c5-4fef-bf58-e8188410605e_637503825593765582.xml',
            'STBC96615325_1597249888210_YFXY9eP.xml',
            'TGTC238e19ce_1603195065008_yJWka80.xml',
            'TWGT0b3b32d1_1600857778793_2gKCmVT_2.xml',
            'FX_PI_01_UK_SCTE_PRODUCTS_COMMON_wef-20220208_20220211-0936.xml',
            'FX_PI_01_UK_SCTE_LINE_FARE_Line-59t@Outbound_wef-20220208_20220211-0936.xml',
        ):
            path = base_path / filename

            with path.open() as open_file:
                command.handle_file(source, open_file, filename)

        tariff = Tariff.objects.get(
            filename="KBUS_FF_ArrivaAdd-on_2Multi_6d7e341a-0680-4397-9b3f-90a290087494_637613495098903655.xml"
        )
        self.assertEqual(str(tariff.valid_between), '[2021-07-08 00:00:00+00:00, 2121-07-08 00:00:00+00:00]')
