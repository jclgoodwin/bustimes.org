import os
import zipfile
from datetime import date
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
# from ...models import (Operator, DataSource, OperatorCode, Service, Region, StopPoint, Journey, StopUsageUsage,
#                        ServiceDate, ServiceLink)
from ...models import Route
from ..commands import import_transxchange


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def clean_up():
    # clean up
    for filename in ('EA.zip', 'S.zip', 'NCSD.zip', 'NW.zip'):
        path = os.path.join(FIXTURES_DIR, filename)
        if os.path.exists(path):
            os.remove(path)


@override_settings(TNDS_DIR=FIXTURES_DIR)
class ImportTransXChangeTest(TestCase):
    command = import_transxchange.Command()

    @classmethod
    @freeze_time('2016-01-01')
    def setUpTestData(cls):
        clean_up()

        # # simulate a Scotland zipfile:
        # cls.write_files_to_zipfile_and_import('S.zip', ['SVRABBN017.xml', 'CGAO305.xml'])

        # # simulate a North West zipfile:
        # cls.write_files_to_zipfile_and_import('NW.zip', ['NW_04_GMN_2_1.xml', 'NW_04_GMN_2_2.xml',
        #                                                  'NW_04_GMS_237_1.xml', 'NW_04_GMS_237_2.xml'])

        # # simulate a National Coach Service Database zip file
        # ncsd_zipfile_path = os.path.join(FIXTURES_DIR, 'NCSD.zip')
        # with zipfile.ZipFile(ncsd_zipfile_path, 'a') as ncsd_zipfile:
        #     for line_name in ('M11A', 'M12'):
        #         file_name = 'Megabus_Megabus14032016 163144_MEGA_' + line_name + '.xml'
        #         cls.write_file_to_zipfile(ncsd_zipfile, os.path.join('NCSD_TXC', file_name))
        #     ncsd_zipfile.writestr(
        #         'IncludedServices.csv',
        #        'Operator,LineName,Dir,Description\nMEGA,M11A,O,Belgravia - Liverpool\nMEGA,M12,O,Shudehill - Victoria'
        #     )
        # call_command(cls.command, ncsd_zipfile_path)

        # # test re-importing a previously imported service again
        # call_command(cls.command, ncsd_zipfile_path)

    @classmethod
    def write_files_to_zipfile_and_import(cls, zipfile_name, filenames):
        zipfile_path = os.path.join(FIXTURES_DIR, zipfile_name)
        with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
            for filename in filenames:
                cls.write_file_to_zipfile(open_zipfile, filename)
        call_command(cls.command, zipfile_path)

    @staticmethod
    def write_file_to_zipfile(open_zipfile, filename):
        open_zipfile.write(os.path.join(FIXTURES_DIR, filename), filename)

    # @classmethod
    # def do_service(cls, filename, region_id):
    #     filename = '%s.xml' % filename
    #     if region_id == 'GB':
    #         region_id = 'NCSD'
    #     cls.command.set_region('%s.zip' % region_id)
    #     path = os.path.join(FIXTURES_DIR, filename)
    #     with open(path) as xml_file:
    #         cls.command.do_service(xml_file, filename)

    # def test_do_service_invalid(self):
    #     """A file with some wrong references should be silently ignored"""
    #     self.do_service('NW_05_PBT_6_1', 'GB')

    # @freeze_time('30 October 2017')
    # def test_do_service_with_empty_pattern(self):
    #     """A file with a JourneyPattern with no JourneyPatternSections should be imported"""
    #     with warnings.catch_warnings(record=True) as caught_warnings:
    #         self.do_service('swe_33-9A-A-y10-2', 'GB')
    #         self.assertEqual(len(caught_warnings), 2)
    #     self.assertTrue(Service.objects.filter(service_code='swe_33-9A-A-y10').exists())

    # def test_service_nw(self):
    #     # 2
    #     service = Service.objects.get(service_code='NW_04_GMN_2_1')
    #     self.assertEqual(service.description, 'intu Trafford Centre - Eccles - Swinton - Bolton')

    #     self.assertEqual(0, service.stopusage_set.all().count())

    # def test_service_nw_2(self):
    #     # Stagecoach Manchester 237
    #     service = Service.objects.get(service_code='NW_04_GMS_237_1')
    #     duplicate = Service.objects.get(service_code='NW_04_GMS_237_2')
    #     ServiceLink.objects.create(from_service=service, to_service=duplicate, how='parallel')

    #     self.assertEqual(service.description, 'Glossop - Stalybridge - Ashton')

    #     with freeze_time('1 September 2017'):
    #         res = self.client.get(service.get_absolute_url())
    #     self.assertContains(res, 'Timetable changes from Sunday 3 September 2017')

    #     with freeze_time('1 October 2017'):
    #         res = self.client.get(service.get_absolute_url())

    #     self.assertNotContains(res, 'Timetable changes from Sunday 3 September 2017')

    #     self.assertEqual(18, len(res.context_data['timetable'].groupings[0].journeys))

    #     with freeze_time('1 October 2017'):
    #         res = self.client.get(service.get_absolute_url() + '?date=2017-10-03')
    #     self.assertEqual(27, len(res.context_data['timetable'].groupings[0].journeys))
    #     self.assertEqual(30, len(res.context_data['timetable'].groupings[1].journeys))

    #     self.assertEqual(0, service.stopusage_set.all().count())
    #     self.assertEqual(1, duplicate.stopusage_set.all().count())

    # @freeze_time('30 December 2016')
    # def test_service_dates(self):
    #     self.assertEqual(14, ServiceDate.objects.count())

    #     # speed up
    #     self.ea_service.current = False
    #     self.ea_service.save()

    #     call_command('generate_service_dates')
    #     self.assertEqual(28, ServiceDate.objects.count())

    #     call_command('generate_service_dates')
    #     self.assertEqual(28, ServiceDate.objects.count())

    @freeze_time('3 October 2016')
    def test_east_anglia(self):
        with self.assertNumQueries(150):
            self.write_files_to_zipfile_and_import('EA.zip', ['ea_21-13B-B-y08-1.xml'])

        service = Route.objects.get(line_name='13B', line_brand='Turquoise Line')

        # self.assertEqual(str(service), '13B - Turquoise Line - Norwich - Wymondham - Attleborough')
        self.assertEqual(service.line_name, '13B')
        self.assertEqual(service.line_brand, 'Turquoise Line')
        self.assertEqual(service.start_date, date(2016, 4, 18))
        self.assertEqual(service.end_date, date(2016, 10, 21))
    #     self.assertEqual(service.outbound_description, 'Norwich - Wymondham - Attleborough')
    #     self.assertEqual(service.inbound_description, 'Attleborough - Wymondham - Norwich')
    #     self.assertEqual(service.operator.first(), self.fecs)
    #     self.assertEqual(
    #         service.get_traveline_link()[0],
    #         'http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST' +
    #         '?line=2113B&lineVer=1&net=ea&project=y08&sup=B&command=direct&outputFormat=0'
    #     )

        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')
        self.assertContains(res, """
            <tr>
                <th>
                    2900N12348
                </th>
                <td>22:55</td>
                <td>19:47</td>
            </tr>
        """, html=True)

    #     # Test the fallback version without a timetable (just a list of stops)
    #     service.show_timetable = False
    #     service.save()
    #     res = self.client.get(service.get_absolute_url())
    #     self.assertContains(res, 'Leys Lane (adj)')
    #     self.assertContains(res, 'Norwich - Wymondham - Attleborough')
    #     self.assertContains(res, 'Attleborough - Wymondham - Norwich')

    #     # Re-import the service, now that the operating period has passed
    #     with freeze_time('2016-10-30'):
    #         call_command(self.command, os.path.join(FIXTURES_DIR, 'EA.zip'))
    #     service.refresh_from_db()
    #     self.assertFalse(service.current)

    # @freeze_time('22 January 2017')
    # def test_do_service_m11a(self):
    #     res = self.client.get('/services/m11a-belgravia-liverpool?date=ceci n\'est pas une date')

    #     service = res.context_data['object']

    #     self.assertEqual(str(service), 'M11A - Belgravia - Liverpool')
    #     self.assertTrue(service.show_timetable)
    #     self.assertEqual(service.operator.first(), self.megabus)
    #     self.assertEqual(
    #         service.get_traveline_link()[0],
    #         'http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST' +
    #         '?line=11M11&sup=A&net=nrc&project=y08&command=direct&outputFormat=0'
    #     )

    #     self.assertEqual(res.context_data['breadcrumb'], [self.gb, self.megabus])
    #     self.assertTemplateUsed(res, 'busstops/service_detail.html')
    #     self.assertContains(res, '<h1>M11A - Belgravia - Liverpool</h1>')
    #     self.assertContains(res, '<option selected value="2017-01-22">Sunday 22 January 2017</option>')
    #     self.assertContains(
    #         res,
    #         """
    #         <td colspan="7">
    #         Book at <a
    #         href="https://www.awin1.com/awclick.php?mid=2678&amp;id=242611&amp;clickref=urlise&amp;p=https%3A%2F%2Fuk.megabus.com"
    #         rel="nofollow">
    #         megabus.com</a> or 0900 1600900 (65p/min + network charges)
    #         </td>
    #         """,
    #         html=True
    #     )
    #     self.assertContains(res, '/js/timetable.min.js')

    # @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    # @freeze_time('1 Dec 2016')
    # def test_do_service_m12(self):
    #     res = self.client.get(self.gb_m12.get_absolute_url())

    #     # The date of the next StopUsageUsage should be used, even though today is 1 Dec 2016
    #     self.assertContains(res, '<option selected value="2017-01-01">Sunday 1 January 2017</option>')

    #     groupings = res.context_data['timetable'].groupings
    #     outbound_stops = [str(row.part.stop) for row in groupings[0].rows]
    #     inbound_stops = [str(row.part.stop) for row in groupings[1].rows]
    #     self.assertEqual(outbound_stops, [
    #         'Belgravia Victoria Coach Station', '049004705400', 'Rugby ASDA', 'Fosse Park ASDA',
    #         'Loughborough Holywell Way', 'Nottingham Broad Marsh Bus Station', 'Meadowhall Interchange',
    #         'Leeds City Centre York Street', 'Bradford City Centre Hall Ings',
    #         'Huddersfield Town Centre Market Street', 'Leeds City Centre Bus Stn',
    #         'Shudehill Interchange', 'Middlesbrough Bus Station Express Lounge', 'Sunderland Interchange',
    #         'Newcastle upon Tyne John Dobson Street',
    #     ])
    #     self.assertEqual(inbound_stops, [
    #         'Huddersfield Town Centre Market Street', 'Bradford City Centre Interchange',
    #         'Newcastle upon Tyne John Dobson Street', 'Sunderland Interchange',
    #         'Middlesbrough Bus Station Express Lounge',  'Leeds City Centre Bus Stn',
    #         'Shudehill Interchange', 'Leeds City Centre York Street', 'Meadowhall Interchange',
    #         'Nottingham Broad Marsh Bus Station', 'Loughborough Holywell Way', 'Fosse Park ASDA',
    #         'Rugby ASDA', '049004705400', 'Victoria Coach Station Arrivals'
    #     ])

    #     with override_settings(TNDS_DIR='this is not a directory'):
    #         # should not be cached (because dummy cache)
    #         with override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}):
    #             res = self.client.get(self.gb_m12.get_absolute_url())
    #         self.assertIsNone(res.context_data['timetable'])

    #         # should be cached
    #         res = self.client.get(self.gb_m12.get_absolute_url())
    #         self.assertEqual('2017-01-01', str(res.context_data['timetable'].date))

    #         # should be cached (even though different date)
    #         res = self.client.get(self.gb_m12.get_absolute_url() + '?date=2017-01-02')
    #         self.assertEqual('2017-01-02', str(res.context_data['timetable'].date))

    # @freeze_time('25 June 2016')
    # def test_do_service_scotland(self):
    #     service = self.sc_service

    #     self.assertEqual(str(service), 'N17 - Aberdeen - Dyce')
    #     self.assertTrue(service.show_timetable)
    #     self.assertEqual(service.operator.first(), self.fabd)
    #     self.assertEqual(
    #         service.get_traveline_link()[0],
    #         'http://www.travelinescotland.com/lts/#/timetables?' +
    #         'timetableId=ABBN017&direction=OUTBOUND&queryDate=&queryTime='
    #     )
    #     self.assertEqual(service.geometry.coords, ((
    #         (53.7423055225, -2.504212506), (53.7398252112, -2.5083672338),
    #         (53.7389877672, -2.5108434749), (53.7425523688, -2.4989239373)
    #     ),))

    #     res = self.client.get(service.get_absolute_url())
    #     self.assertEqual(res.context_data['breadcrumb'], [self.sc, self.fabd])
    #     self.assertTemplateUsed(res, 'busstops/service_detail.html')
    #     self.assertContains(res, '<td rowspan="63">then every 30 minutes until</td>', html=True)

    #     # Within operating period, but with no journeys
    #     res = self.client.get(service.get_absolute_url() + '?date=2026-04-18')
    #     self.assertContains(res, 'Sorry, no journeys found for Saturday 18 April 2026')

    #     # Test the fallback version without a timetable (just a list of stops)
    #     service.show_timetable = False
    #     service.save()
    #     res = self.client.get(service.get_absolute_url())
    #     self.assertContains(res, 'Outbound')
    #     self.assertContains(res, """
    #         <li class="OTH">
    #             <a href="/stops/639004554">Witton Park (opp)</a>
    #         </li>
    #     """, html=True)

    # @freeze_time('25 June 2016')
    # def test_do_service_wales(self):
    #     service = Service.objects.get(service_code='CGAO305')
    #     service_code = service.servicecode_set.first()

    #     self.assertEqual(service_code.scheme, 'Traveline Cymru')
    #     self.assertEqual(service_code.code, '305MFMWA1')

    #     service.region = self.w
    #     service.source = None
    #     service.save()

    #     response = self.client.get(service.get_absolute_url())
    #     self.assertEqual(response.context_data['links'], [{
    #         'url': 'https://www.traveline.cymru/timetables/?routeNum=305&direction_id=0&timetable_key=305MFMWA1',
    #         'text': 'Timetable on the Traveline Cymru website'
    #     }])

    # def test_departures(self):
    #     self.assertEqual(6, Journey.objects.filter(service='M12_MEGA').count())
    #     self.assertEqual(9, StopUsageUsage.objects.filter(journey__service='M12_MEGA').count())

    #     # Megabus services have been imported twice, but there should only be one of each StopUsage
    #     self.assertEqual(1, StopPoint.objects.filter(service='M12_MEGA').count())

    #     # This should be the first journey (some earlier journeys should have been deleted)
    #     journey = Journey.objects.first()
    #     self.assertEqual('M12 - Shudehill - Victoria 2017-01-01 01:00:00+00:00', str(journey))

    #     stop_usage_usage = StopUsageUsage.objects.first()
    #     self.assertEqual('2017-01-01 02:20:00+00:00', str(stop_usage_usage.datetime))
    #     self.assertEqual('Kingston District Centre (o/s) 2017-01-01 02:20:00+00:00', str(stop_usage_usage))

    #     self.assertEqual(0, Journey.objects.filter(service__region='S').count())
    #     self.assertEqual(0, Journey.objects.filter(service__region='EA').count())

    # def test_combine_date_time(self):
    #     combine_date_time = generate_departures.combine_date_time
    #     self.assertEqual(str(combine_date_time(date(2017, 3, 26), time(0, 10))), '2017-03-26 00:10:00+00:00')
    #     # Clocks go forward 1 hour at 1am. Not sure what buses *actually* do, but pretending
    #     self.assertEqual(str(combine_date_time(date(2017, 3, 26), time(1, 10))), '2017-03-26 02:10:00+01:00')
    #     self.assertEqual(str(combine_date_time(date(2017, 3, 27), time(0, 10))), '2017-03-27 00:10:00+01:00')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        clean_up()
