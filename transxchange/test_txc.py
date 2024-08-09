"""Tests for timetables and date ranges"""

import xml.etree.cElementTree as ET
from datetime import date
from django.test import TestCase
from . import txc


class DateRangeTest(TestCase):
    """Tests for DateRanges"""

    def test_single_date(self):
        """Test a DateRange starting and ending on the same date"""
        element = ET.fromstring(
            """
            <DateRange>
                <StartDate>2001-05-01</StartDate>
                <EndDate>2001-05-01</EndDate>
            </DateRange>
        """
        )
        date_range = txc.DateRange(element)
        self.assertEqual(str(date_range), "2001-05-01")
        self.assertFalse(date_range.contains(date(1994, 5, 4)))
        self.assertTrue(date_range.contains(date(2001, 5, 1)))
        self.assertFalse(date_range.contains(date(2005, 5, 4)))

    def test_range(self):
        element = ET.fromstring(
            """
            <OperatingPeriod>
                <StartDate>2001-05-01</StartDate>
                <EndDate>2002-05-01</EndDate>
            </OperatingPeriod>
        """
        )
        date_range = txc.DateRange(element)
        self.assertEqual(str(date_range), "2001-05-01 to 2002-05-01")

    def test_operating_profile(self):
        element = ET.fromstring(
            """
            <OperatingProfile>
                <RegularDayType>
                    <DaysOfWeek>
                        <NotWednesday />
                    </DaysOfWeek>
                </RegularDayType>
            </OperatingProfile>
        """
        )
        operating_profile = txc.OperatingProfile(element, None)
        self.assertEqual(
            str(operating_profile.regular_days),
            "[Monday, Tuesday, Thursday, Friday, Saturday, Sunday]",
        )

        element = ET.fromstring(
            """
          <OperatingProfile>
            <RegularDayType>
              <DaysOfWeek>
                <Weekend />
              </DaysOfWeek>
            </RegularDayType>
          </OperatingProfile>
        """
        )
        operating_profile = txc.OperatingProfile(element, None)
        self.assertEqual(str(operating_profile.regular_days), "[Saturday, Sunday]")
