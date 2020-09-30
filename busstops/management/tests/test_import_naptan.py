"""Tests for importing NaPTAN data
"""
import os
import vcr
from mock import patch
from warnings import catch_warnings
from django.core.management import call_command
from django.test import TestCase, override_settings
from ...models import Region, AdminArea, StopPoint, Locality, Service, StopUsage, DataSource
from ..commands import import_stop_areas, import_stops, import_stops_in_area, import_stop_area_hierarchy


DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(DIR, 'fixtures')


@override_settings(DATA_DIR=FIXTURES_DIR)
class UpdateNaptanTest(TestCase):
    """Test the update_naptan command
    """
    def test_handle(self):
        naptan_dir = os.path.join(FIXTURES_DIR, 'NaPTAN')
        if not os.path.exists(naptan_dir):
            os.mkdir(naptan_dir)
        zipfile_path = os.path.join(naptan_dir, 'naptan.zip')

        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'naptan.yml')):
            call_command('update_naptan')

        source = DataSource.objects.get(name='NaPTAN')
        self.assertEqual(source.settings[0]['LastUpload'], '03/09/2020')

        with open(zipfile_path) as open_file:
            self.assertEqual(open_file.read(), 'this is all the data')

        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'naptan.yml')):
            with patch('busstops.management.commands.update_naptan.Command.get_data') as get_data:
                call_command('update_naptan')
                get_data.assert_not_called()

        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'naptan.yml')):
            source.settings[0]['LastUpload'] = '01/09/2020'
            source.save(update_fields=['settings'])

            call_command('update_naptan')

        source.refresh_from_db()
        self.assertEqual(source.settings[0]['LastUpload'], '03/09/2020')

        with open(zipfile_path) as open_file:
            self.assertEqual(open_file.read(), 'this is the shetland data')

        # simulate a problem with the region-specific NaPTAN download, so all regions are downloaded
        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'naptan-error.yml')):
            with override_settings(DATA_DIR=FIXTURES_DIR):
                call_command('update_naptan')
        with open(zipfile_path) as open_file:
            self.assertEqual(open_file.read(), 'these pretzels are making me thirsty again')

        # clean up afterwards
        os.remove(zipfile_path)
        os.rmdir(naptan_dir)


class ImportStopsTest(TestCase):
    def test_correct_case(self):
        self.assertEqual(import_stops.correct_case('B&Q'), 'B&Q')
        self.assertEqual(import_stops.correct_case('P&R'), 'P&R')
        self.assertEqual(import_stops.correct_case('A1(M)'), 'A1(M)')
        self.assertEqual(import_stops.correct_case('YKK'), 'YKK')
        self.assertEqual(import_stops.correct_case('EE'), 'EE')
        self.assertEqual(import_stops.correct_case('PH'), 'PH')
        self.assertEqual(import_stops.correct_case('NUMBER 45'), 'Number 45')
        self.assertEqual(import_stops.correct_case('KING STREET'), 'King Street')
        self.assertEqual(import_stops.correct_case('DWP DEPOT'), 'DWP Depot')


class ImportNaptanTest(TestCase):
    """Test the import_stops, import_stop_areas, import_stops_in_area and
    import_stop_area_hierarchy commands
    """

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(id='GB', name='Great Britain')
        cls.admin_area = AdminArea.objects.create(id=34, atco_code=2, region_id='GB')
        cls.admin_area_2 = AdminArea.objects.create(id=91, atco_code=290, region_id='GB')
        cls.locality_1 = Locality.objects.create(id='E0054410', name='Baglan', admin_area_id=34)
        cls.locality_2 = Locality.objects.create(id='N0078801', name='Port Talbot', admin_area_id=34)

        # for two stops in Briningham corrected by the correct_stops
        cls.locality_3 = Locality.objects.create(id='E0048637', name='Briningham', admin_area_id=34)

        command = import_stops.Command()
        for filename in ('Stops.csv', 'StopPoints.csv'):
            command.input = os.path.join(FIXTURES_DIR, filename)
            command.handle()

        cls.stop_area = import_stop_areas.Command().handle_row({
            'GridType': 'U',
            'Status': 'act',
            'Name': 'Buscot Copse',
            'AdministrativeAreaCode': '034',
            'StopAreaType': 'GPBS',
            'NameLang': '',
            'StopAreaCode': '030G50780001',
            'Easting': '460097',
            'Modification': 'new',
            'ModificationDateTime': '2015-02-13T15:31:00',
            'CreationDateTime': '2015-02-13T15:31:00',
            'RevisionNumber': '0',
            'Northing': '171718'
        })
        cls.stop_area_parent = import_stop_areas.Command().handle_row({
            'Status': 'act',
            'Name': 'Buscot Wood',
            'AdministrativeAreaCode': '034',
            'StopAreaType': 'GPBS',
            'StopAreaCode': '030G50780002',
            'Easting': '460097',
            'Northing': '171718'
        })

        import_stops_in_area.Command().handle_row({
            'StopAreaCode': '030G50780001',
            'AtcoCode': '5820AWN26274',
        })
        import_stops_in_area.Command().handle_row({
            'StopAreaCode': '030G50780001',
            'AtcoCode': '5820AWN26438',
        })

        import_stop_area_hierarchy.Command().handle_row({
            'ChildStopAreaCode': '030G50780001',
            'ParentStopAreaCode': '030G50780002',
        })

        cls.service = Service.objects.create(line_name='44', description='Port Talbot Circular',
                                             date='2004-04-04', region_id='GB', service_code='44')
        StopUsage.objects.create(service=cls.service, stop_id='5820AWN26274', order=0)  # Legion
        StopUsage.objects.create(service=cls.service, stop_id='5820AWN26361', order=1)  # Parkway
        StopUsage.objects.create(service=cls.service, stop_id='5820AWN26438', order=2)

    def test_stops(self):
        legion = StopPoint.objects.get(pk='5820AWN26274')
        self.assertEqual(str(legion), 'The Legion (o/s) ↖')
        self.assertEqual(legion.landmark, 'Port Talbot British Legion')
        self.assertEqual(legion.street, 'Talbot Road')  # converted from 'TALBOT ROAD'
        self.assertEqual(legion.crossing, 'Eagle Street')
        self.assertEqual(legion.get_heading(), 315)

        plaza = StopPoint.objects.get(pk='5820AWN26259')
        self.assertEqual(plaza.get_qualified_name(), 'Port Talbot Plaza')
        self.assertEqual(str(plaza), 'Plaza ↘')
        self.assertEqual(plaza.landmark, 'Port Talbot British Legion')
        self.assertEqual(plaza.crossing, 'Eagle Street')
        self.assertEqual(plaza.get_heading(), 135)

        club = StopPoint.objects.get(pk='5820AWN26438')
        # backtick should be replaced and 'NE - bound' should be normalised
        self.assertEqual(str(club), "Ty'n y Twr Club (NE-bound) ↗")

        parkway_station = StopPoint.objects.get(pk='5820AWN26361')
        self.assertEqual(parkway_station.crossing, '')  # '---' should be removed
        self.assertEqual(parkway_station.indicator, '')

        res = self.client.get('/localities/N0078801')
        self.assertContains(res, 'Services')
        self.assertContains(res, '44 - Port Talbot Circular')

        irish_stop = StopPoint.objects.get(atco_code='7000B6310001')
        self.assertEqual(irish_stop.common_name, 'Belcoo')
        self.assertEqual(irish_stop.street, 'N16')

        stop = StopPoint.objects.get(atco_code='2900B482')
        self.assertAlmostEqual(stop.latlong.x, 1.0261288054215825)
        self.assertAlmostEqual(stop.latlong.y, 52.86800772276406)

    def test_stop_areas(self):
        """Given a row, does handle_row return a StopArea object with the correct field values?
        """
        self.assertEqual(self.stop_area.id, '030G50780001')
        self.assertEqual(self.stop_area.name, 'Buscot Copse')
        self.assertEqual(self.stop_area.stop_area_type, 'GPBS')
        self.assertEqual(self.stop_area.admin_area, self.admin_area)
        self.assertTrue(self.stop_area.active)

        self.assertEqual(self.stop_area_parent.id, '030G50780002')
        self.assertEqual(str(self.stop_area_parent), 'Buscot Wood')

    def test_stops_in_area(self):
        legion = StopPoint.objects.get(pk='5820AWN26274')
        self.assertEqual(self.stop_area, legion.stop_area)

        with catch_warnings(record=True) as caught_warnings:
            import_stops_in_area.Command().handle_row({
                'StopAreaCode': 'poo',
                'AtcoCode': 'poo'
            })
            self.assertEqual(1, len(caught_warnings))

        self.assertContains(self.client.get('/stops/5820AWN26361'), 'Port Talbot Circular')

        res = self.client.get('/stops/5820AWN26274')
        self.assertContains(res, 'On Talbot Road, near Eagle Street, near Port Talbot British Legion')
        self.assertContains(res, 'Services')
        self.assertContains(res, '44')
        self.assertContains(res, 'Port Talbot Circular')
        self.assertContains(res, """
            <div class="aside">
                <h2>Nearby stops</h2>
                <ul class="has-smalls">
                    <li>
                        <a href="/stops/5820AWN26438">
                            <span>Ty&#x27;n y Twr Club (NE-bound) ↗</span>
                            <small>44</small>
                        </a>
                    </li>
                </ul>
            </div>
        """, html=True)

    def test_stop_area_hierarchy(self):
        self.assertIsNone(self.stop_area.parent)
        self.assertIsNone(self.stop_area_parent.parent)

        self.stop_area.refresh_from_db()
        self.stop_area_parent.refresh_from_db()

        self.assertEqual(self.stop_area.parent, self.stop_area_parent)
        self.assertIsNone(self.stop_area_parent.parent)

    def test_correct_stops(self):
        """Test that correct_stops correctly moves a stop in Briningham from the church to the village green"""
        stop = StopPoint.objects.get(atco_code='2900B484')
        self.assertEqual('Briningham, opp church', stop.get_qualified_name())

        call_command('correct_stops')

        stop.refresh_from_db()
        self.assertEqual('Briningham, opp green', stop.get_qualified_name())
