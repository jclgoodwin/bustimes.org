import zipfile
import vcr
import time_machine
import datetime
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.core.management import call_command
from busstops.models import Region, AdminArea, StopPoint, Service, Operator
from ...models import Route
from ..commands import import_gtfs


FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'


def make_zipfile(directory, collection):
    dir_path = FIXTURES_DIR / f'google_transit_{collection}'
    feed_path = Path(directory) / f'google_transit_{collection}.zip'
    with zipfile.ZipFile(feed_path, 'a') as open_zipfile:
        for item in dir_path.iterdir():
            open_zipfile.write(item, item.name)


@override_settings(DATA_DIR=FIXTURES_DIR)
@time_machine.travel(datetime.datetime(2019, 8, 30))
class GTFSTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Make a GTFS feed (a zip file containing some text files)."""

        cls.leinster = Region.objects.create(
            id='LE',
            name='Leinster'
        )
        cls.ulster = Region.objects.create(
            id='UL',
            name='Ulster'
        )
        cls.dublin = AdminArea.objects.create(
            id=822,
            atco_code=822,
            region_id='LE',
            name='Dublin'
        )
        cls.south_dublin = AdminArea.objects.create(
            id=823,
            atco_code=823,
            region_id='LE'
        )
        cls.donegal = AdminArea.objects.create(
            id=853,
            atco_code=853,
            region_id='UL'
        )

        # Create an existing operator (with a slightly different name) to test that it is re-used
        Operator.objects.create(id=132, name='Seumas Doherty', region=cls.leinster)

        # this should get updated later
        StopPoint.objects.create(atco_code="8220DB000759", common_name="Estadio Donnybrook", active=True)

    def test_import_gtfs(self):
        with TemporaryDirectory() as directory:

            make_zipfile(directory, 'seamusdoherty')
            make_zipfile(directory, 'mortons')

            with override_settings(DATA_DIR=directory):
                with vcr.use_cassette(str(FIXTURES_DIR / 'google_transit_ie.yaml')) as cassette:
                    with self.assertLogs('bustimes.management.commands.import_gtfs', 'INFO'):
                        with self.assertLogs('bustimes.utils', 'ERROR') as cm:
                            call_command('import_gtfs', '--force', '-v2')

                            cassette.rewind()

                            # import a second time - test that it's OK if stuff already exists
                            call_command('import_gtfs', '--force')

        self.assertEqual(cm.output, [
            'ERROR:bustimes.utils:<Response [404]> '
            'https://www.transportforireland.ie/transitData/google_transit_seamusdoherty.zip',
            'ERROR:bustimes.utils:<Response [404]> '
            'https://www.transportforireland.ie/transitData/google_transit_seamusdoherty.zip'
        ])

        # stops
        self.assertEqual(StopPoint.objects.count(), 75)
        stop = StopPoint.objects.get(atco_code='822000153')
        self.assertEqual(stop.common_name, 'Terenure Library')
        self.assertEqual(stop.admin_area_id, 822)

        self.assertEqual(Operator.objects.count(), 2)
        self.assertEqual(Operator.objects.filter(service__current=True).distinct().count(), 2)

        # small timetable
        with time_machine.travel('2017-06-07'):
            response = self.client.get('/services/165')
        timetable = response.context_data['timetable']
        self.assertEqual(str(timetable.groupings[0]), 'Outbound')
        self.assertEqual(str(timetable.groupings[1]), 'Inbound')
        self.assertFalse(timetable.origins_and_destinations)
        self.assertEqual(str(timetable.groupings[0].rows[0].times), '[07:45]')
        self.assertEqual(str(timetable.groupings[0].rows[4].times), '[07:52]')
        self.assertEqual(str(timetable.groupings[0].rows[6].times), '[08:01]')
        self.assertEqual(str(timetable.groupings[1].rows[0].times), '[17:20]')
        self.assertEqual(str(timetable.groupings[1].rows[6].times), '[17:45]')
        self.assertEqual(str(timetable.groupings[1].rows[-1].times), '[18:25]')
        self.assertEqual(len(timetable.groupings[0].rows), 18)
        self.assertEqual(len(timetable.groupings[1].rows), 14)

        self.assertContains(
            response,
            '<a href="https://www.transportforireland.ie/transitData/PT_Data.html">Transport for Ireland</a>'
        )

        for day in (
            datetime.date(2017, 6, 11),
            datetime.date(2017, 12, 25),
            datetime.date(2015, 12, 3),
            datetime.date(2020, 12, 3)
        ):
            with time_machine.travel(day):
                with self.assertNumQueries(14):
                    response = self.client.get(f'/services/165?date={day}')
                timetable = response.context_data['timetable']
                self.assertEqual(day, timetable.date)
                self.assertEqual(timetable.groupings, [])

        # big timetable
        service = Service.objects.get(route__code='21-963-1-y11-1')
        timetable = service.get_timetable(datetime.date(2017, 6, 7))
        self.assertEqual(str(timetable.groupings[0].rows[0].times), "['', 10:15, '', 14:15, 17:45]")
        self.assertEqual(str(timetable.groupings[0].rows[1].times), "['', 10:20, '', 14:20, 17:50]")
        self.assertEqual(str(timetable.groupings[0].rows[2].times), "['', 10:22, '', 14:22, 17:52]")

        self.assertTrue(service.geometry)

        self.assertEqual(str(service.source), 'seamusdoherty GTFS')

        # admin area
        res = self.client.get(self.dublin.get_absolute_url())
        self.assertContains(res, 'Bus services in Dublin', html=True)
        self.assertContains(res, '/services/165')

        # check that the common_name and latlong of the existing stop were updated
        stop = StopPoint.objects.get(atco_code="8220DB000759")
        self.assertEqual(stop.common_name, "Donnybrook, Old Wesley Rugby Football Club")
        self.assertEqual(str(stop.latlong), "SRID=4326;POINT (-6.23334551683733 53.3203488508422)")

    def test_download_if_modified(self):
        path = Path('poop.txt')
        url = 'https://bustimes.org/static/js/global.js'

        if path.exists():
            path.unlink()

        cassette = str(FIXTURES_DIR / 'download_if_modified.yaml')

        with vcr.use_cassette(cassette, match_on=['uri', 'headers']):
            changed, when = import_gtfs.download_if_changed(path, url)
            self.assertTrue(changed)
            self.assertEqual(str(when), '2020-06-02 07:35:34+00:00')

            with patch('os.path.getmtime', return_value=1593870909.0) as getmtime:
                changed, when = import_gtfs.download_if_changed(path, url)
                self.assertTrue(changed)
                self.assertEqual(str(when), '2020-06-02 07:35:34+00:00')
                getmtime.assert_called_with(path)

        self.assertTrue(path.exists())
        path.unlink()

    def test_handle(self):
        with patch('bustimes.management.commands.import_gtfs.download_if_changed', return_value=(False, None)):
            call_command('import_gtfs', 'mortons')
        self.assertFalse(Route.objects.all())

        with patch('bustimes.management.commands.import_gtfs.download_if_changed', return_value=(True, None)):
            with self.assertLogs('bustimes.management.commands.import_gtfs', 'INFO') as cm:
                with self.assertRaises(FileNotFoundError):
                    call_command('import_gtfs', 'mortons')

        self.assertEqual(cm.output, ['INFO:bustimes.management.commands.import_gtfs:mortons None'])

        self.assertFalse(Route.objects.all())
