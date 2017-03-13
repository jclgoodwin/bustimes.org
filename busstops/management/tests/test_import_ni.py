"""Tests for importing Northern Ireland stops and services
"""
import os
import vcr
from freezegun import freeze_time
from django.test import TestCase, override_settings
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
        cls.command.set_up()
        cls.stop_1 = StopPoint.objects.create(atco_code='700000015364', locality_centre=False, active=True)
        cls.stop_2 = StopPoint.objects.create(atco_code='700000000916', locality_centre=False, active=True)
        cls.stop_3 = StopPoint.objects.create(atco_code='700000001567', locality_centre=False, active=True)

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
        self.assertIsNone(self.command.direction)
        self.command.handle_line(line)
        self.assertEqual(self.command.direction, 'O')

    def test_route_description(self):
        self.assertEqual(len(Service.objects.filter(service_code='1A_MET')), 0)
        self.assertIsNone(self.command.service_code)
        self.assertEqual(self.command.services, {})

        line = 'QDNMET 1A  OCity Centre - Carnmoney - Fairview Road - Glenville                 \n'
        self.command.handle_line(line)

        service = Service.objects.get(service_code='1A_MET')
        self.assertEqual(service.line_name, '1A')
        self.assertEqual(service.description, 'City Centre - Carnmoney - Fairview Road - Glenville')
        self.assertEqual(self.command.service_code, '1A_MET')
        self.assertEqual(self.command.services, {'1A_MET': {'I': {}, 'O': {}}})

        service.save()

    def test_stop(self):
        self.command.handle_open_file(('QO7000000153640545UQST1  \n',
                                       'QI70000000175005470547BR2 T1  \n',
                                       'QI70000000091605480548B   T0  \n',
                                       'QT7000000015670609   T1  \n'))

        self.assertEqual(self.command.deferred_stop_codes, ['700000001750'])

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
    @freeze_time('4 May 2017')
    def setUpTestData(cls):
        Region.objects.create(id='NI')
        StopPoint.objects.bulk_create(
            (StopPoint(atco_code=atco_code, locality_centre=False, active=True) for atco_code in (
                '700000012165', '700000012648', '700000012668', '700000012701', '700000012729', '700000012730',
                '700000012731', '700000012732', '700000012733', '700000012734', '700000012735', '700000012736',
                '700000012737', '700000012738', '700000012739', '700000012740', '700000012741', '700000012742',
                '700000012743', '700000012744', '700000012745', '700000012746', '700000012747', '700000012748',
                '700000012749', '700000012750', '700000012757', '700000012778', '700000012779', '700000012780',
                '700000012781', '700000012782', '700000012783', '700000015377'
            ))
        )
        Service.objects.create(service_code='95c_ULB', date='2016-01-01', region_id='NI', current=True)
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

        self.assertEqual(270, StopUsageUsage.objects.all().count())

    @freeze_time('12 Mar 2017')
    def test_timetable(self):
        response = self.client.get('/services/95c_ULB')
        self.assertContains(response, '<label for="show-all-stops-1-1">Show all stops</label>')
        self.assertContains(response, '<h2>Post Office - Roslea - Buscentre - Enniskillen </h2>')
        self.assertContains(response, '<h2>Enniskillen, Buscentre - Roslea, Post Office </h2>')
        self.assertEqual(response.context_data['timetables'][0].groupings[0].rows[0].times, ['07:35', '07:35'])
        self.assertEqual(response.context_data['timetables'][0].groupings[0].rows[-2].times, ['     ', '08:20'])
        self.assertEqual(response.context_data['timetables'][0].groupings[0].rows[-1].times, ['08:20', '     '])
