"""Tests for importing NaPTAN data
"""

import os
import vcr
from django.test import TestCase
from ...models import Region, AdminArea, StopPoint, Locality, Service, StopUsage
from ..commands import (update_naptan, import_stop_areas, import_stops, import_stops_in_area,
                        import_stop_area_hierarchy)


DIR = os.path.dirname(os.path.abspath(__file__))


class UpdateNaptanTest(TestCase):
    """Test the update_naptan command
    """
    command = update_naptan.Command()

    def test_get_old_rows(self):
        self.assertIsNone(self.command.get_old_rows())

    def test_get_diff(self):
        new_rows = [{
            'id': 1,
            'cell': [
                'S',
                'Aberdeen',
                '639',
                '07/06/2016',
                '1354',
                '143',
                '0',
                '0',
                '0',
                '0',
                '0',
                'V2',
                '7/17/2016'
            ]
        }]
        self.assertEqual(self.command.get_diff(new_rows, None), (['S'], ['639']))
        self.assertEqual(self.command.get_diff(new_rows, new_rows), ([], []))

    def test_handle(self):
        with vcr.use_cassette(os.path.join(DIR, 'fixtures', 'naptan.yml')):
            with self.assertRaises(TypeError):
                self.command.handle()


class ImportNaptanTest(TestCase):
    """Test the import_stops, import_stop_areas, import_stops_in_area and
    import_stop_area_hierarchy commands
    """

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(id='GB', name='Great Britain')
        cls.admin_area = AdminArea.objects.create(id=34, atco_code=2, region_id='GB')
        cls.locality_1 = Locality.objects.create(id='E0054410', name='Baglan', admin_area_id=34)
        cls.locality_2 = Locality.objects.create(id='N0078801', name='Port Talbot', admin_area_id=34)

        command = import_stops.Command()
        for filename in ('Stops.csv', 'StopPoints.csv'):
            command.input = os.path.join(DIR, 'fixtures', filename)
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

    def test_stops(self):
        legion = StopPoint.objects.get(pk='5820AWN26274')
        self.assertEqual(str(legion), 'The Legion (o/s)')
        self.assertEqual(legion.landmark, 'Port Talbot British Legion')
        self.assertEqual(legion.street, 'Talbot Road')  # converted from 'TALBOT ROAD'
        self.assertEqual(legion.crossing, 'Eagle Street')
        self.assertEqual(legion.get_heading(), 315)

        plaza = StopPoint.objects.get(pk='5820AWN26259')
        self.assertEqual(plaza.get_qualified_name(), 'Port Talbot Plaza')
        self.assertEqual(plaza.landmark, 'Port Talbot British Legion')
        self.assertEqual(plaza.crossing, 'Eagle Street')
        self.assertEqual(plaza.get_heading(), 135)

        club = StopPoint.objects.get(pk='5820AWN26438')
        # backtick should be replaced and 'NE - bound' should be normalised
        self.assertEqual(str(club), "Ty'n y Twr Club (NE-bound)")

        parkway_station = StopPoint.objects.get(pk='5820AWN26361')
        self.assertEqual(parkway_station.crossing, '')  # '---' should be removed
        self.assertEqual(parkway_station.indicator, '')

        locality_request = self.client.get('/localities/N0078801')
        self.assertContains(locality_request, 'Services')
        self.assertContains(locality_request, '44 - Port Talbot Circular')

        irish_stop = StopPoint.objects.get(atco_code='7000B6310001')
        self.assertEqual(irish_stop.common_name, 'Belcoo')
        self.assertEqual(irish_stop.street, 'N16')

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

        if hasattr(self, 'assertLogs'):
            with self.assertLogs() as context_manager:
                import_stops_in_area.Command().handle_row({
                    'StopAreaCode': 'poo',
                    'AtcoCode': 'poo'
                })
                self.assertEqual(1, len(context_manager.output))
                self.assertEqual(context_manager.output[0][:32], 'ERROR:busstops.management.comman')

        with vcr.use_cassette(os.path.join(DIR, 'fixtures', '5820AWN26361.yaml')):
            self.assertContains(self.client.get('/stops/5820AWN26361'), 'Port Talbot Circular')

        with vcr.use_cassette(os.path.join(DIR, 'fixtures', '5820AWN26274.yaml')):
            legion_request = self.client.get('/stops/5820AWN26274')
            self.assertContains(legion_request, 'On Talbot Road, near Eagle Street, near Port Talbot ' +
                                'British Legion')
        self.assertContains(legion_request, 'Services')
        self.assertContains(legion_request, '44 - Port Talbot Circular')
        self.assertContains(legion_request, """
            <div class="aside box">
                <h2>Nearby stops</h2>
                <ul>
                    <li itemscope itemtype="https://schema.org/BusStop">
                        <a href="/stops/5820AWN26438">
                            <span itemprop="name">Ty&#39;n y Twr Club (NE-bound)</span>
                            <span itemprop="geo" itemscope itemtype="https://schema.org/GeoCoordinates">
                                <meta itemprop="latitude" content="51.6171316877" />
                                <meta itemprop="longitude" content="-3.8000765776" />
                            </span>
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
