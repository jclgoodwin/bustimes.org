import os
import xml.etree.cElementTree as ET
import timetable
from django.test import TestCase
from busstops.models import Service


class TimetableTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.service = Service.objects.create(
            pk='NE_130_PC4736_572',
            line_name='572',
            description='Ravenstonedale - Barnard Castle',
            region_id='NE',
            date='2016-05-05'
        )

    def test_get_filename(self):
        self.assertEqual(timetable.get_filenames(self.service, None), ('NE_130_PC4736_572.xml',))


class DateRangeTest(TestCase):
    def test_single_date(self):
        element = ET.fromstring("""
            <DateRange xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2001-05-01</EndDate>
            </DateRange>
        """)
        date_range = timetable.DateRange(element)
        self.assertEqual(str(date_range), '1 May 2001')
        self.assertFalse(date_range.starts_in_future())

    def test_past_range(self):
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2002-05-01</EndDate>
            </OperatingPeriod>
        """)
        date_range = timetable.DateRange(element)
        self.assertEqual(str(date_range), '2001-05-01 to 2002-05-01')


class OperatingPeriodTest(TestCase):
    def test_single_date(self):
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2001-05-01</EndDate>
            </OperatingPeriod>
        """)
        operating_period = timetable.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'on 1 May 2001')
        self.assertFalse(operating_period.starts_in_future())

    def test_open_ended(self):
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2021-09-01</StartDate>
            </OperatingPeriod>
        """)
        operating_period = timetable.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 September 2021')
        self.assertTrue(operating_period.starts_in_future())

    def test_future_long_range(self):
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2021-09-01</StartDate>
                <EndDate>2056-02-02</EndDate>
            </OperatingPeriod>
        """)
        operating_period = timetable.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 September 2021 to 2 February 2056')
        self.assertTrue(operating_period.starts_in_future())

    def test_future_medium_range(self):
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2056-02-01</StartDate>
                <EndDate>2056-06-02</EndDate>
            </OperatingPeriod>
        """)
        operating_period = timetable.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 February to 2 June 2056')
        self.assertTrue(operating_period.starts_in_future())

    def test_future_short_range(self):
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2056-02-01</StartDate>
                <EndDate>2056-02-05</EndDate>
            </OperatingPeriod>
        """)
        operating_period = timetable.OperatingPeriod(element)
        self.assertEqual(str(operating_period), 'from 1 to 5 February 2056')
        self.assertTrue(operating_period.starts_in_future())

    def test_past_range(self):
        element = ET.fromstring("""
            <OperatingPeriod xmlns="http://www.transxchange.org.uk/">
                <StartDate>2001-05-01</StartDate>
                <EndDate>2002-05-01</EndDate>
            </OperatingPeriod>
        """)
        operating_period = timetable.OperatingPeriod(element)
        self.assertEqual(str(operating_period), '')
