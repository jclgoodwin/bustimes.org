"""Tests for importing Ireland stops and gazetteer
"""
import os
import warnings
import zipfile
from unittest.mock import patch, call
from tempfile import TemporaryDirectory
from django.test import TestCase
from django.core.management import call_command
from ...models import Region, AdminArea, Locality, StopPoint


class ImportIrelandTest(TestCase):
    """Test the import_ie_nptg and import_ie_nptg command
    """
    def test_ie_nptg_and_naptan(self):
        directory = os.path.dirname(os.path.abspath(__file__))
        fixtures_dir = os.path.join(directory, 'fixtures')

        # NPTG (places):

        call_command('import_ie_nptg', os.path.join(fixtures_dir, 'ie_nptg.xml'))

        regions = Region.objects.all().order_by('name')
        self.assertEqual(len(regions), 5)
        self.assertEqual(regions[0].name, 'Connacht')
        self.assertEqual(regions[2].name, 'Munster')

        areas = AdminArea.objects.all().order_by('name')
        self.assertEqual(len(areas), 40)

        self.assertEqual(areas[0].name, 'Antrim')
        self.assertEqual(areas[0].region.name, 'Northern Ireland')

        self.assertEqual(areas[2].name, 'Carlow')
        self.assertEqual(areas[2].region.name, 'Leinster')

        localities = Locality.objects.all().order_by('name')
        self.assertEqual(len(localities), 3)

        self.assertEqual(localities[0].name, 'Dangan')
        self.assertEqual(localities[0].admin_area.name, 'Galway City')
        self.assertAlmostEqual(localities[0].latlong.x, -9.077645)
        self.assertAlmostEqual(localities[0].latlong.y, 53.290138)

        self.assertEqual(localities[2].name, 'Salthill')
        self.assertEqual(localities[2].admin_area.name, 'Galway City')
        self.assertAlmostEqual(localities[2].latlong.x, -9.070427)
        self.assertAlmostEqual(localities[2].latlong.y, 53.262565)

        # NaPTAN (stops):

        with TemporaryDirectory() as temp_dir:
            zipfile_path = os.path.join(temp_dir, 'ie_naptan.zip')
            with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
                open_zipfile.write(os.path.join(fixtures_dir, 'ie_naptan.xml'))

            with warnings.catch_warnings(record=True) as caught_warnings:
                with patch('builtins.print') as mocked_print:
                    call_command('import_ie_naptan_xml', zipfile_path)

        mocked_print.assert_has_calls([
            call('700'), call('700'), call('700'), call('E0853142'), call('E0824005')
        ])

        self.assertEqual(str(caught_warnings[0].message), 'Stop 700000004096 has an unexpected property: Crossing')
        self.assertEqual(str(caught_warnings[1].message), 'Stop 8250B1002801 has no location')

        stops = StopPoint.objects.all().order_by('atco_code')
        self.assertEqual(len(stops), 6)
        self.assertEqual(stops[0].atco_code, '700000004096')
        self.assertEqual(stops[0].common_name, 'Rathfriland')
        self.assertEqual(stops[0].stop_type, '')
        self.assertEqual(stops[0].bus_stop_type, '')
        self.assertEqual(stops[0].timing_status, '')
        self.assertAlmostEqual(stops[0].latlong.x, -6.15849970528097)
        self.assertAlmostEqual(stops[0].latlong.y, 54.236552528081)

        stop = stops.get(atco_code='700000015422')
        self.assertEqual(stop.common_name, 'Europa Buscentre Belfast')
        self.assertEqual(stop.street, 'Glengall Street')
        self.assertEqual(stop.crossing, '')
        self.assertEqual(stop.indicator, 'in')
        self.assertEqual(stop.bearing, '')
        self.assertEqual(stop.timing_status, 'OTH')
        self.assertAlmostEqual(stop.latlong.x, -5.93626793184173)
        self.assertAlmostEqual(stop.latlong.y, 54.5950542848164)

        stop = stops.get(atco_code='8460TR000124')
        self.assertEqual(stop.common_name, "Supermac's")
        self.assertEqual(stop.street, 'Bridge Street')
        self.assertEqual(stop.crossing, '')
        self.assertEqual(stop.indicator, 'opp')
        self.assertEqual(stop.bearing, '')
        self.assertEqual(stop.timing_status, '')
        self.assertEqual(stop.stop_type, 'TXR')
        self.assertAlmostEqual(stop.latlong.x, -9.05469898181141)
        self.assertAlmostEqual(stop.latlong.y, 53.2719763661735)
        self.assertEqual(stop.admin_area_id, 846)
        self.assertEqual(stop.locality_id, 'E0846001')

        with patch('builtins.print') as mocked_print:
            call_command('import_ie_transxchange', os.path.join(fixtures_dir, 'ie_transxchange.xml'))
        mocked_print.assert_called_with('E0824005', 'Bal-briggan')
        # self.assertEqual(Locality.objects.get(id='E0824005').name, 'Bal-briggan')
