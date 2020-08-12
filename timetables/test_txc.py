"""Tests for timetables and date ranges"""
import xml.etree.cElementTree as ET
from datetime import date
from freezegun import freeze_time
from django.test import TestCase
from . import txc


FIXTURES_DIR = './busstops/management/tests/fixtures/'


class DescriptionTest(TestCase):
    def test_correct_description(self):
        self.assertEqual(txc.correct_description('Penryn College - Stitians'), 'Penryn College - Stithians')
        self.assertEqual(txc.correct_description('Sutton Benger- Swindon'), 'Sutton Benger - Swindon')


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
        """An OperatingPeriod shorter than 7 days should be displayed"""
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2015-02-27</StartDate>
                <EndDate>2015-03-01</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'until 1 March 2015')

    @freeze_time('2 February 2015')
    def test_long_range(self):
        """An OperatingPeriod longer than 7 days should not be displayed"""
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
                <StartDate>2002-05-31</StartDate>
                <EndDate>2002-06-01</EndDate>
            </OperatingPeriod>
        """)
        operating_period = txc.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'until 1 June 2002')


class StopTest(TestCase):
    def test_is_at(self):
        stop = txc.Stop(ET.fromstring("""
            <AnnotatedStopPointRef xmlns="http://www.transxchange.org.uk/">
                <StopPointRef>1800SB45781</StopPointRef>
                <CommonName>Wythenshawe Hospital</CommonName>
                <LocalityName>Newall Green</LocalityName>
                <LocalityQualifier>Wythenshawe</LocalityQualifier>
            </AnnotatedStopPointRef>
        """))
        self.assertEqual(stop.is_at('wythenshawe-hospital'), 2)
        self.assertEqual(stop.is_at('wythenshawe'), 1)
