"""Tests for importing Northern Ireland stops and services
"""
import os
import vcr
from datetime import date, time
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import StopPoint, Region, AdminArea, Service, StopUsage, StopUsageUsage
from ..commands import import_ni_stops, enhance_ni_stops, import_ni_services, generate_departures
from .test_import_nptg import ImportNPTGTest


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportNornIronTest(TestCase):
    """Test the import_ni_stops command
    """
    @classmethod
    def setUpTestData(cls):
        ImportNPTGTest.do_import(import_ni_stops.Command(), 'bus-stop-list-february-2016')

        cls.mount_eagles = StopPoint.objects.get(atco_code='700000000000')
        cls.ni_stops = StopPoint.objects.filter(atco_code__startswith='700')
        cls.ni = Region(id='NI', name='Northern Ireland').save()

        # Create a dummy active service
        cls.service = Service.objects.create(service_code='DUMMY', date='2016-12-27', region_id='NI')
        # Use a stop which is near a landmark
        StopUsage.objects.create(service=cls.service, stop_id='700000000007', order=0)

        AdminArea.objects.create(region_id='NI', id='700', atco_code='700', name='Down')

    def test_stops(self):
        self.assertEqual(self.mount_eagles.indicator, 'outward')
        self.assertEqual(self.mount_eagles.common_name, 'Mount Eagles')

        self.assertEqual(len(self.ni_stops), 9)

    def test_enhance_stops(self):
        command = enhance_ni_stops.Command()
        command.delay = 0
        with vcr.use_cassette(os.path.join(DIR, 'fixtures', 'enhance_ni_stops.yaml')):
            command.handle()

        stop = StopPoint.objects.get(atco_code='700000000007')

        self.assertEqual(stop.street, 'Newtownards Road')
        self.assertEqual(stop.landmark, 'Dr Pitt Memorial Park')
        self.assertEqual(stop.town, '')


class ImportNIServicesTest(TestCase):
    """Test the import_ni_services command
    """
    command = import_ni_services.Command()

    @classmethod
    def setUpTestData(cls):
        cls.norn_iron = Region.objects.create(id='NI', name='Northern Ireland')
        with override_settings(DATA_DIR=os.path.join(DIR, 'fixtures')):
            call_command('import_ni_services')
        StopPoint.objects.create(atco_code='700000015364', locality_centre=False, active=True)
        StopPoint.objects.create(atco_code='700000001750', locality_centre=False, active=True)
        StopPoint.objects.create(atco_code='700000000916', locality_centre=False, active=True)
        StopPoint.objects.create(atco_code='700000001567', locality_centre=False, active=True)

    def test_file_header(self):
        line = 'ATCO-CIF0500Metro                           OMNITIMES       20160802144451\n'
        self.assertEqual(self.command.get_file_header(line), {
            'file_type': 'ATCO-CIF',
            'version': '0500',
            'file_originator': 'Metro                           ',
            'source_product': 'OMNITIMES       ',
            'production_datetime': '20160802144451'
        })

    def test_journey_header(self):
        line = 'QSNMET 0510  20160901201706301111100 X1A                        O\n'
        self.assertEqual(self.command.get_journey_header(line), {
            'transaction_type': 'N',
            'operator': 'MET ',
            'unique_journey_identifier': '0510  ',
            'direction': 'O\n',
        })

    def test_service(self):
        service = Service.objects.get(service_code='1A_MET')
        self.assertEqual(service.line_name, '1A')
        self.assertEqual(service.description, 'City Centre - Carnmoney - Fairview Road - Glenville')

        stops = service.stopusage_set.all()
        self.assertEqual(4, len(stops))
        for stop in stops:
            self.assertEqual(stop.direction, 'Outbound')

    def test_stop(self):
        self.command.handle_open_file(('QO7000000153640545UQST1  \n',
                                       'QI70000000175005470547BR2 T1  \n',
                                       'QI70000000091605480548B   T0  \n',
                                       'QT7000000015670609   T1  \n'))

        self.assertEqual(self.command.deferred_stop_codes,
                         ['700000015364', '700000001750', '700000000916', '700000001567'])

        self.command.handle_open_file(['QLN700000001750Royal Avenue (Castle Court)\n',
                                       'QBN700000001750333746  374496\n'])
        self.assertEqual(self.command.deferred_stops['700000001750'].common_name,
                         'Royal Avenue (Castle Court)')
        self.assertEqual(self.command.deferred_stops['700000001750'].latlong.x, 333746.0)
        self.assertEqual(self.command.deferred_stops['700000001750'].latlong.y, 374496.0)

        self.assertEqual(self.command.stop_usages[0].stop_id, '700000015364')
        self.assertEqual(self.command.stop_usages[0].direction, 'Outbound')
        self.assertEqual(self.command.stop_usages[0].order, 0)
        self.assertEqual(self.command.stop_usages[1].stop_id, '700000001750')
        self.assertEqual(self.command.stop_usages[1].direction, 'Outbound')
        self.assertEqual(self.command.stop_usages[1].order, 1)
        self.assertEqual(self.command.stop_usages[2].stop_id, '700000000916')
        self.assertEqual(self.command.stop_usages[2].direction, 'Outbound')
        self.assertEqual(self.command.stop_usages[2].order, 1)
        self.assertEqual(self.command.stop_usages[3].stop_id, '700000001567')
        self.assertEqual(self.command.stop_usages[3].direction, 'Outbound')
        self.assertEqual(self.command.stop_usages[3].order, 2)


@override_settings(DATA_DIR=os.path.join(DIR, 'fixtures'))
class ServiceTest(TestCase):
    """Test departures and timetables for Northern Ireland
    """
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='NI')
        # Create 95c_ULB stops:
        StopPoint.objects.bulk_create(
            StopPoint(atco_code='7000000' + suffix, locality_centre=False, active=True) for suffix in (
                '12165', '12648', '12668', '12701', '12729', '12730', '12731', '12732', '12733', '12734', '12735',
                '12736', '12737', '12738', '12739', '12740', '12741', '12742', '12743', '12744', '12745', '12746',
                '12747', '12748', '12749', '12750', '12757', '12778', '12779', '12780', '12781', '12782', '12783',
                '15377'
            )
        )
        # Create 212_GLE stops:
        StopPoint.objects.bulk_create(
            StopPoint(atco_code='7000000' + suffix, locality_centre=False, active=True) for suffix in (
                '15363', '15678', '14232', '14230', '13311', '15229', '15679', '13331', '13214', '15739', '15746',
                '13305', '15747', '14231', '15677', '00792'
            )
        )
        Service.objects.bulk_create([
            Service(service_code='212_GLE', date='2016-01-01', region_id='NI', current=True),
            Service(service_code='95_ULB', date='2016-01-01', region_id='NI', current=True),
            Service(service_code='95c_ULB', date='2016-01-01', region_id='NI', current=True, show_timetable=True)
        ])
        with freeze_time('3 May 2017'):
            generate_departures.handle_region(Region(id='NI'))
        with freeze_time('4 May 2017'):
            generate_departures.handle_region(Region(id='NI'))

    """Test the generate_departures command
    """
    @freeze_time('3 May 2017 22:50')
    def test_departures(self):
        response = self.client.get('/stops/700000012733')
        self.assertContains(response, '<td>18:32</td>', 6, html=True)
        self.assertContains(response, '95c_ULB', 6)
        self.assertContains(response, '<h3>Friday</h3>', 1)
        self.assertContains(response, '<h3>Monday</h3>', 1)
        self.assertContains(response, '<h3>Tuesday</h3>', 1)
        self.assertContains(response, '<h3>Wednesday</h3>', 1)
        self.assertContains(response, '<h3>Thursday</h3>', 2)
        self.assertNotContains(response, 'Saturday')

        for count, search in (
            (270, {'journey__service': '95c_ULB'}),
            (3134, {'journey__service': '212_GLE'}),
            (412, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-04'}),
            (442, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-05'}),
            (328, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-06'}),  # Sat
            (304, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-07'}),  # Sun
            (412, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-08'}),  # Mon
            (412, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-09'}),
            (412, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-10'}),
            (412, {'journey__service': '212_GLE', 'datetime__date': '2017-05-10'}),
            (412, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-11'}),
            (412, {'journey__service': '212_GLE', 'datetime__date': '2017-05-11'}),
            (0, {'journey__service': '212_GLE', 'journey__datetime__date': '2017-05-12'}),
            (2, {'journey__service': '212_GLE', 'datetime__date': '2017-05-12'}),
            (0, {'journey__service': '212_GLE', 'journey__datetime__date__gte': '2017-05-13'}),
            (0, {'journey__service': '212_GLE', 'datetime__date__gte': '2017-05-13'}),
        ):
            self.assertEqual(count, StopUsageUsage.objects.filter(**search).count())

    def test_combine_date_time(self):
        self.assertEqual(str(generate_departures.combine_date_time(date(2017, 10, 29), time(1, 20))),
                         '2017-10-29 01:20:00+01:00')

    @freeze_time('12 Mar 2017')
    def test_timetable(self):
        response = self.client.get('/services/95c_ulb')
        self.assertContains(response, '<option selected value="2017-05-04">Thursday 4 May 2017</option>')
        self.assertContains(response, '<label for="show-all-stops-1">Show all stops</label>')
        self.assertContains(response, '<h2>Post Office - Roslea - Buscentre - Enniskillen </h2>')
        self.assertContains(response, '<h2>Enniskillen, Buscentre - Roslea, Post Office </h2>')
        self.assertEqual(response.context_data['timetable'].groupings[0].rows[0].times, ['07:35', '07:35'])
        self.assertEqual(response.context_data['timetable'].groupings[0].rows[-2].times, ['     ', '08:20'])
        self.assertEqual(response.context_data['timetable'].groupings[0].rows[-1].times, ['08:20', '     '])

        response = self.client.get('/services/95c_ULB.xml')
        self.assertContains(response, '"Post Office - Roslea - Buscentre - Enniskillen"')
