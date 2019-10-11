import os
import zipfile
from freezegun import freeze_time
from django.test import TestCase
from django.core.management import call_command
from django.contrib.gis.geos import Point
from busstops.models import Region, Operator, Service, StopPoint
from ...models import Route


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def clean_up():
    # clean up
    path = os.path.join(FIXTURES_DIR, 'ulb.zip')
    if os.path.exists(path):
        os.remove(path)


def write_file_to_zipfile(open_zipfile, filename):
    open_zipfile.write(os.path.join(FIXTURES_DIR, filename), filename)


def write_files_to_zipfile(zipfile_path, filenames):
    with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
        for filename in filenames:
            write_file_to_zipfile(open_zipfile, filename)


class ImportAtcoCifTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ni = Region.objects.create(pk='NI', name='Northern Ireland')
        cls.gle = Operator.objects.create(pk='GLE', name='Goldline Express', region=cls.ni)

        StopPoint.objects.bulk_create(
            StopPoint(atco_code, latlong=Point(0, 0), active=True) for atco_code in (
                '700000015363',
                '700000015687',
                '700000004923',
                '700000005645'
            )
        )

    def test_ulsterbus(self):
        zipfile_path = os.path.join(FIXTURES_DIR, 'ulb.zip')

        clean_up()
        write_files_to_zipfile(zipfile_path, ['218 219.cif'])
        with freeze_time('2019-10-09'):
            call_command('import_atco_cif', zipfile_path)
        clean_up()

        self.assertEqual(5, Route.objects.count())
        self.assertEqual(5, Service.objects.count())

        with freeze_time('2019-10-01'):
            with self.assertNumQueries(13):
                response = self.client.get('/services/219a-belfast-europa-buscentre-antrim-buscentre')
        self.assertContains(response, '<option selected value="2019-10-09">Wednesday 9 October 2019</option>')
        self.assertNotContains(response, 'Sunday')
        self.assertContains(response, '<label for="show-all-stops-1">Show all stops</label>')
        self.assertContains(response, '<h1>219a - Belfast, Europa Buscentre - Antrim, Buscentre</h1>')

        with freeze_time('2019-10-01'):
            with self.assertNumQueries(11):
                response = self.client.get('/services/219a-belfast-europa-buscentre-antrim-buscentre?date=2019-10-01')
        self.assertContains(response, '<option selected value="2019-10-01">Tuesday 1 October 2019</option>')
        self.assertNotContains(response, 'Sunday')
        self.assertContains(response, '<label for="show-all-stops-1">Show all stops</label>')
        self.assertContains(response, '<h1>219a - Belfast, Europa Buscentre - Antrim, Buscentre</h1>')

        with freeze_time('2019-08-12'):
            with self.assertNumQueries(9):
                response = self.client.get('/services/219a-belfast-europa-buscentre-antrim-buscentre?date=2019-08-12')
        self.assertContains(response, '<option selected value="2019-08-12">Monday 12 August 2019</option>')
        self.assertNotContains(response, 'Sunday')
        self.assertContains(response, 'Sorry, no journeys found for Monday 12 August 2019')

        with freeze_time('2019-08-12'):
            with self.assertNumQueries(11):
                response = self.client.get('/services/219a-belfast-europa-buscentre-antrim-buscentre?date=2019-12-25')
        self.assertContains(response, '<option selected value="2019-12-25">Wednesday 25 December 2019</option>')
        self.assertNotContains(response, 'Sunday')
