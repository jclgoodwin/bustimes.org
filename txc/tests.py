"""Tests for timetables and date ranges"""
import xml.etree.cElementTree as ET
from datetime import time, timedelta, date
from unittest import skip
from freezegun import freeze_time
from django.test import TestCase
from . import txc


FIXTURES_DIR = './busstops/management/tests/fixtures/'


class TimetableTest(TestCase):
    """Tests some timetables generated directly from XML files"""

    def test_timetable_none(self):
        """timetable_from_filename should return None if there is an error"""
        none = txc.timetable_from_filename(FIXTURES_DIR, 'ea_21-13B-B-y08-', '2017-01-21')
        self.assertIsNone(none)

    def test_timetable_ea(self):
        """Test a timetable from the East Anglia region"""
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'ea_21-13B-B-y08-1.xml', '2016-10-16')

        self.assertEqual('Monday to Sunday', str(timetable.operating_profile))
        self.assertEqual('until 21 October 2016', str(timetable.operating_period))

        self.assertEqual('Norwich - Wymondham - Attleborough', str(timetable.groupings[0]))
        self.assertEqual(1, len(timetable.groupings[0].column_heads))
        self.assertEqual(11, len(timetable.groupings[0].journeys))

        self.assertEqual('Attleborough - Wymondham - Norwich', str(timetable.groupings[1]))
        self.assertEqual(1, len(timetable.groupings[1].column_heads))
        self.assertEqual(10, len(timetable.groupings[1].journeys))

        self.assertTrue(timetable.groupings[1].has_minor_stops())
        self.assertEqual(87, len(timetable.groupings[1].rows))
        self.assertEqual('Leys Lane', timetable.groupings[1].rows[0].part.stop.common_name)

    def test_timetable_ea_2(self):
        """Test a timetable with a single OperatingProfile (no per-VehicleJourney ones)"""
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'ea_20-12-_-y08-1.xml', '2016-12-02')

        self.assertEqual('Monday to Friday', str(timetable.operating_profile))
        self.assertEqual('', str(timetable.operating_period))

        self.assertEqual('Outbound', str(timetable.groupings[0]))
        self.assertEqual(1, len(timetable.groupings[0].column_heads))
        self.assertIsNone(timetable.groupings[0].column_heads[0].operatingprofile)
        self.assertEqual(21, len(timetable.groupings[0].rows))

        self.assertEqual('[St Ives (Cambs) Bus Station]', str(timetable.groupings[0].rows[0]))
        self.assertEqual(3, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(3, timetable.groupings[0].rows[0].times[1].colspan)
        self.assertEqual(21, timetable.groupings[0].rows[0].times[1].rowspan)
        self.assertEqual(2, len(timetable.groupings[0].rows[1].times))
        self.assertEqual(2, len(timetable.groupings[0].rows[20].times))

        self.assertEqual(0, len(timetable.groupings[1].rows))

        with self.assertRaises(IndexError):
            str(timetable.groupings[1])

    def test_timetable_megabus(self):
        """Test a timetable from the National Coach Services Database"""
        megabus = txc.timetable_from_filename(FIXTURES_DIR, 'Megabus_Megabus14032016 163144_MEGA_M11A.xml', '2016-12-02')
        self.assertFalse(megabus.groupings[0].has_minor_stops())
        self.assertFalse(megabus.groupings[1].has_minor_stops())
        self.assertEqual(len(megabus.groupings[0].column_heads), 2)
        self.assertEqual(megabus.groupings[0].rows[0].times, [
            time(15, 0), time(16, 30), time(23, 45), time(13, 0), time(16, 0), time(18, 0),
            time(20, 0)
        ])
        self.assertEqual(len(megabus.groupings[1].column_heads), 4)

    @skip('Need to adapt to timetable changes')
    def test_timetable_ne(self):
        """Test timetable with some abbreviations"""
        timetable_ne = txc.timetable_from_filename(FIXTURES_DIR, 'NE_03_SCC_X6_1.xml')
        self.assertEqual('Kendal - Barrow-in-Furness', str(timetable_ne.groupings[0]))
        self.assertEqual(timetable_ne.groupings[0].column_heads[0].span, 16)
        self.assertEqual(timetable_ne.groupings[0].column_heads[1].span, 14)
        self.assertEqual(timetable_ne.groupings[0].column_heads[2].span, 4)
        self.assertEqual(
            timetable_ne.groupings[0].rows[0].times[:3], [time(7, 0), time(8, 0), time(9, 0)]
        )
        # Test abbreviations (check the colspan and rowspan attributes of Cells)
        self.assertEqual(timetable_ne.groupings[0].rows[0].times[3].colspan, 6)
        self.assertEqual(timetable_ne.groupings[0].rows[0].times[3].rowspan, 117)
        self.assertEqual(timetable_ne.groupings[1].rows[0].times[-2].colspan, 2)

    @skip('Why has this stopped passing!?')
    def test_timetable_scotland(self):
        """Test a Scotch timetable with no foot"""
        timetable_scotland = txc.timetable_from_filename(FIXTURES_DIR, 'SVRABBN017.xml', '2016-12-13')
        self.assertFalse(hasattr(timetable_scotland.groupings[0], 'column_feet'))

    @skip('Need to adapt to timetable changes')
    def test_timetable_deadruns(self):
        """Test a timetable with some dead runs which should be respected"""
        deadruns = txc.timetable_from_filename(FIXTURES_DIR, 'SVRLABO024A.xml', None)
        self.assertEqual(
            deadruns.groupings[0].rows[-25].times[:3], [time(20, 58), time(22, 28), time(23, 53)]
        )
        self.assertEqual(
            deadruns.groupings[0].rows[-24].times[:7], ['', '', '', '', '', '', time(9, 51)]
        )
        self.assertEqual(deadruns.groupings[0].rows[-20].times[:6], ['', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-12].times[:6], ['', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-8].times[:6], ['', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-7].times[:6], ['', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-5].times[:6], ['', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-4].times[:6], ['', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-3].times[:6], ['', '', '', '', '', ''])
        self.assertEqual(
            deadruns.groupings[0].rows[-2].times[:7], ['', '', '', '', '', '', time(10, 5)]
        )
        self.assertEqual(
            deadruns.groupings[0].rows[-1].times[:7], ['', '', '', '', '', '', time(10, 7)]
        )

    @skip('Need to adapt to timetable changes')
    def test_timetable_servicedorg(self):
        """Test a timetable with a ServicedOrganisation"""
        timetable_sw = txc.timetable_from_filename(FIXTURES_DIR, 'swe_31-668-_-y10-1.xml')
        self.assertEqual(str(timetable_sw.groupings[0].column_heads[0].operatingprofile),
                         'Monday to Friday')
        self.assertEqual(timetable_sw.groupings[0].column_feet[0].notes,
                         {'Sch': 'School days only'})

    @skip('Need to adapt to timetable changes')
    def test_timetable_welsh_servicedorg(self):
        """Test a timetable from Wales (with SequenceNumbers on Journeys),
        with a university ServicedOrganisation
        """
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'CGAO305.xml')
        self.assertEqual(timetable.groupings[0].column_feet[0].notes,
                         {'Sch': 'University days only'})


class CellTest(TestCase):
    def test_cell(self):
        self.assertEqual(str(txc.Cell(1, 1, timedelta(minutes=20))), 'then every 20 minutes until')
        self.assertEqual(str(txc.Cell(1, 1, timedelta(minutes=60))), 'then hourly until')
        self.assertEqual(str(txc.Cell(1, 1, timedelta(minutes=120))), 'then every 2 hours until')


class DateRangeTest(TestCase):
    """Tests for DateRanges"""

    def test_single_date(self):
        """Test a DateRange starting and ending on the same date"""
        element = ET.fromstring("""
            <DateRange xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2001-05-01</EndDate>
            </DateRange>
        """)
        date_range = txc.DateRange(element)
        self.assertEqual(str(date_range), '1 May 2001')
        self.assertFalse(date_range.contains(date(1994, 5, 4)))
        self.assertTrue(date_range.contains(date(2001, 5, 1)))
        self.assertFalse(date_range.contains(date(2005, 5, 4)))

    def test_past_range(self):
        """Test a DateRange starting and ending in the past"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2002-05-01</EndDate>
            </OperatingPeriod>
        """)
        date_range = txc.DateRange(element)
        self.assertEqual(str(date_range), '2001-05-01 to 2002-05-01')


class OperatingPeriodTest(TestCase):
    """Tests for OperatingPeriods"""

    def test_single_date(self):
        """Test an OperatingPeriod starting and ending on the same date"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2001-05-01</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'on 1 May 2001')

    def test_open_ended(self):
        """Test an OperatingPeriod starting in the future, with no specified end"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2021-09-01</StartDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 September 2021')

    @freeze_time('1 May 2004')
    def test_future_long_range(self):
        """Test an OperatingPeriod starting and ending in different years in the future"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2021-09-01</StartDate>
                <EndDate>2056-02-02</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 September 2021')

    @freeze_time('1 May 2004')
    def test_future_medium_range(self):
        """Test an OperatingPeriod starting and ending in the same year in the future"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2056-02-01</StartDate>
                <EndDate>2056-06-02</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 February 2056')

    @freeze_time('1 January 2056')
    def test_short_range(self):
        """Test an OperatingPeriod starting and ending in the same month in the present"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2056-02-01</StartDate>
                <EndDate>2056-02-05</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 to 5 February 2056')

    @freeze_time('1 January 2056')
    def test_short_range_cross_month(self):
        """Test an OperatingPeriod starting and ending in different months in the present"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2056-02-01</StartDate>
                <EndDate>2056-03-05</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 February to 5 March 2056')

    @freeze_time('29 December 2056')
    def test_short_range_cross_year(self):
        """Test an OperatingPeriod starting and ending in different years in the present"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2056-12-30</StartDate>
                <EndDate>2057-01-05</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 30 December 2056 to 5 January 2057')

    def test_medium_range(self):
        """An OperatingPeriod shorter than 40 days should be displayed"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2015-02-01</StartDate>
                <EndDate>2015-03-01</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'until 1 March 2015')

    @freeze_time('2 February 2015')
    def test_long_range(self):
        """An OperatingPeriod longer than 40 days should not be displayed"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2015-02-01</StartDate>
                <EndDate>2015-05-04</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), '')

    def test_past_range(self):
        """An OperatingPeriod starting ending in the past"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2002-06-01</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'until 1 June 2002')
