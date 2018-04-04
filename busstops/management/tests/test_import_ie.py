"""Tests for importing Ireland stops and gazetteer
"""
import os
import warnings
import zipfile
from django.test import TransactionTestCase
from django.core.management import call_command
from ...models import Region, AdminArea, Locality, StopPoint
from ..commands import import_ie_naptan_csv


DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(DIR, 'fixtures')
ZIPFILE_PATH = os.path.join(FIXTURES_DIR, 'ie_naptan.zip')


class ImportIrelandTest(TransactionTestCase):
    """Test the import_ie_nptg and import_ie_nptg command
    """
    @classmethod
    def setUp(cls):
        call_command('import_ie_nptg', os.path.join(FIXTURES_DIR, 'ie_nptg.xml'))

        with zipfile.ZipFile(ZIPFILE_PATH, 'a') as open_zipfile:
            open_zipfile.write(os.path.join(FIXTURES_DIR, 'ie_naptan.xml'))

        with warnings.catch_warnings(record=True) as caught_warnings:
            call_command('import_ie_naptan_xml', ZIPFILE_PATH)
            cls.caught_warnings = caught_warnings

        os.remove(ZIPFILE_PATH)

    def test_warnings(self):
        self.assertEqual(str(self.caught_warnings[0].message), 'Stop 700000004096 has an unexpected property: Crossing')
        self.assertEqual(str(self.caught_warnings[1].message), 'Stop 8250B1002801 has no location')

    def test_regions(self):
        regions = Region.objects.all().order_by('name')
        self.assertEqual(len(regions), 5)
        self.assertEqual(regions[0].name, 'Connacht')
        self.assertEqual(regions[2].name, 'Munster')

    def test_areas(self):
        areas = AdminArea.objects.all().order_by('name')
        self.assertEqual(len(areas), 41)

        self.assertEqual(areas[0].atco_code, 700)
        self.assertEqual(areas[0].name, '')
        self.assertEqual(areas[0].region.name, 'Northern Ireland')

        self.assertEqual(areas[1].name, 'Antrim')
        self.assertEqual(areas[1].region.name, 'Northern Ireland')

        self.assertEqual(areas[3].name, 'Carlow')
        self.assertEqual(areas[3].region.name, 'Leinster')

    def test_localities(self):
        localities = Locality.objects.all().order_by('name')
        self.assertEqual(len(localities), 5)
        self.assertEqual(localities[0].name, '')

        self.assertEqual(localities[1].name, '')

        self.assertEqual(localities[2].name, 'Dangan')
        self.assertEqual(localities[2].admin_area.name, 'Galway City')
        self.assertEqual(localities[2].latlong.x, -9.077645)
        self.assertEqual(localities[2].latlong.y, 53.290138)

        self.assertEqual(localities[4].name, 'Salthill')
        self.assertEqual(localities[4].admin_area.name, 'Galway City')
        self.assertEqual(localities[4].latlong.x, -9.070427)
        self.assertEqual(localities[4].latlong.y, 53.262565)

    def test_stops_from_xml(self):
        stops = StopPoint.objects.all().order_by('atco_code')
        self.assertEqual(len(stops), 6)
        self.assertEqual(stops[0].atco_code, '700000004096')
        self.assertEqual(stops[0].common_name, 'Rathfriland')
        self.assertEqual(stops[0].stop_type, '')
        self.assertEqual(stops[0].bus_stop_type, '')
        self.assertEqual(stops[0].timing_status, '')
        self.assertEqual(stops[0].latlong.x, -6.15849970528097)
        self.assertEqual(stops[0].latlong.y, 54.236552528081)

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

    def test_stops_from_csv(self):
        import_ie_naptan_csv.Command().handle_row({
            'Stop number': '17159',
            'Name without locality': 'Baxter',
            'Locality': 'Galway',
            'Locality number': 'E0846001',
            'Code': 'YYY',
            'Name': 'Chutney',
            'NaPTAN stop class': 'BCT',
            'NaPTANId': '8460TR000124',
            'Easting': '529650',
            'Northing': '725146'
        })
        stop = StopPoint.objects.get(atco_code='8460TR000124')

        self.assertEqual(stop.common_name, "Supermac's")  # Not modified
        self.assertEqual(stop.street, 'Bridge Street')
        self.assertEqual(stop.indicator, 'opp')
        self.assertEqual(stop.stop_type, 'BCT')  # Modified (not sure it should be)
        self.assertAlmostEqual(stop.latlong.x, -9.054698981718873)
        self.assertAlmostEqual(stop.latlong.y, 53.27197636346384)
        self.assertEqual(stop.admin_area_id, 846)
        self.assertEqual(stop.locality_id, 'E0846001')

        import_ie_naptan_csv.Command().handle_row({
            'Easting': '617392',
            'Name': 'Forte Retail Park',
            'Northing': '910970',
            'Locality number': '99032868',
            'Name without locality': 'Forte Retail Park',
            'Locality': 'Leck (Donegal)',
            'NaPTAN stop class': 'BCT',
            'Code': '1',
            'NaPTANId': '853000249',
            'Stop number': '191'
        })
        stop = StopPoint.objects.get(atco_code='853000249')
        self.assertEqual(stop.common_name, 'Forte Retail Park')
        self.assertEqual(stop.locality.name, 'Leck')
        self.assertEqual(stop.locality.qualifier_name, 'Donegal')

        with warnings.catch_warnings(record=True) as caught_warnings:
            import_ie_naptan_csv.Command().handle_row({
                'Stop number': '14440',
                'Name without locality': "Saint Paul's Crescent",
                'Locality': 'Balbriggan',
                'Locality number': 'E0824005',
                'Code': '1',
                'Name': 'Church',
                'NaPTAN stop class': 'BCT',
                'NaPTANId': '8250B1002801',
                'Easting': '',
                'Northing': ''
            })
            self.assertTrue(' has no location' in str(caught_warnings[0].message))
        stop = StopPoint.objects.get(atco_code='8250B1002801')
        self.assertEqual(stop.indicator, '1')

        # Should run without an error:
        import_ie_naptan_csv.Command().handle_row({'NaPTANId': ''})

    def test_transxchange(self):
        self.assertEqual(Locality.objects.get(id='E0824005').name, '')
        call_command('import_ie_transxchange', os.path.join(FIXTURES_DIR, 'ie_transxchange.xml'))
        self.assertEqual(Locality.objects.get(id='E0824005').name, 'Balbriggan')
