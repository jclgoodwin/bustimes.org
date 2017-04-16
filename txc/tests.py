"""Tests for timetables and date ranges"""
import xml.etree.cElementTree as ET
from datetime import time, timedelta, date
from freezegun import freeze_time
from django.test import TestCase
from . import txc


FIXTURES_DIR = './busstops/management/tests/fixtures/'


class TimetableTest(TestCase):
    """Tests some timetables generated directly from XML files"""

    def test_timetable_none(self):
        """timetable_from_filename should return None if there is an error"""
        none = txc.timetable_from_filename(FIXTURES_DIR, 'ea_21-13B-B-y08-', date(2017, 1, 21))
        self.assertIsNone(none)

    def test_timetable_ea(self):
        """Test a timetable from the East Anglia region"""
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'ea_21-13B-B-y08-1.xml', date(2016, 10, 16))

        self.assertEqual('Monday to Sunday', str(timetable.operating_profile))
        self.assertEqual('', str(timetable.operating_period))

        self.assertEqual('Norwich - Wymondham - Attleborough', str(timetable.groupings[0]))
        self.assertEqual(11, len(timetable.groupings[0].journeys))

        self.assertEqual('Attleborough - Wymondham - Norwich', str(timetable.groupings[1]))
        self.assertEqual(10, len(timetable.groupings[1].journeys))

        self.assertTrue(timetable.groupings[1].has_minor_stops())
        self.assertEqual(87, len(timetable.groupings[1].rows))
        self.assertEqual('Leys Lane', timetable.groupings[1].rows[0].part.stop.common_name)

    @freeze_time('1 April 2017')
    def test_timetable_ea_2(self):
        """Test a timetable with a single OperatingProfile (no per-VehicleJourney ones)"""
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'ea_20-12-_-y08-1.xml', date(2016, 12, 2))

        self.assertEqual('Monday to Friday', str(timetable.operating_profile))
        self.assertEqual('', str(timetable.operating_period))

        self.assertEqual('Outbound', str(timetable.groupings[0]))
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

        # Test operating profile days of non operation
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'ea_20-12-_-y08-1.xml', date(2016, 12, 28))
        self.assertEqual(0, len(timetable.groupings[0].rows[0].times))

    def test_timetable_megabus(self):
        """Test a timetable from the National Coach Services Database"""
        megabus = txc.timetable_from_filename(FIXTURES_DIR, 'Megabus_Megabus14032016 163144_MEGA_M11A.xml',
                                              date(2016, 12, 2))
        self.assertFalse(megabus.groupings[0].has_minor_stops())
        self.assertFalse(megabus.groupings[1].has_minor_stops())
        self.assertEqual(megabus.groupings[0].rows[0].times,
                         [time(13, 0), time(15, 0), time(16, 0), time(16, 30), time(18, 0), time(20, 0), time(23, 45)])

    def test_timetable_ne(self):
        """Test timetable with some abbreviations"""
        timetable_ne = txc.timetable_from_filename(FIXTURES_DIR, 'NE_03_SCC_X6_1.xml', date(2016, 12, 15))
        self.assertEqual('Kendal - Barrow-in-Furness', str(timetable_ne.groupings[0]))
        self.assertEqual(
            timetable_ne.groupings[0].rows[0].times[:3], [time(7, 0), time(8, 0), time(9, 0)]
        )
        # Test abbreviations (check the colspan and rowspan attributes of Cells)
        self.assertEqual(timetable_ne.groupings[0].rows[0].times[3].colspan, 6)
        self.assertEqual(timetable_ne.groupings[0].rows[0].times[3].rowspan, 117)
        self.assertEqual(timetable_ne.groupings[1].rows[0].times[:7],
                         [time(5, 20), time(6, 20), time(7, 15), time(8, 10), time(9, 10), time(10, 10), time(11, 10)])

    def test_timetable_scotland(self):
        """Test a Scotch timetable with no foot"""
        timetable_scotland = txc.timetable_from_filename(FIXTURES_DIR, 'SVRABBN017.xml', date(2017, 1, 28))
        self.assertEqual(timetable_scotland.groupings[0].column_feet, {})

    def test_timetable_deadruns(self):
        """Test a timetable with some dead runs which should be respected"""
        deadruns = txc.timetable_from_filename(FIXTURES_DIR, 'SVRLABO024A.xml', None)
        self.assertEqual(deadruns.groupings[0].rows[-25].times[-3:], [time(22, 28), time(23, 53), time(23, 53)])
        self.assertEqual(deadruns.groupings[0].rows[-24].times[-9:], [time(18, 51), '', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-12].times[-9:], [time(19, 0), '', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-8].times[-9:], [time(19, 2), '', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-7].times[-9:], [time(19, 3), '', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-5].times[-9:], [time(19, 4), '', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-4].times[-9:], [time(19, 4), '', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-3].times[-9:], [time(19, 5), '', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-2].times[-8:], ['', '', '', '', '', '', '', ''])
        self.assertEqual(deadruns.groupings[0].rows[-1].times[-8:], ['', '', '', '', '', '', '', ''])

        # Three journeys a day on weekdays
        deadruns = txc.timetable_from_filename(FIXTURES_DIR, 'SVRLABO024A.xml', date(2017, 4, 13))
        self.assertEqual(3, len(deadruns.groupings[0].rows[0].times))

        # Several journeys a day on bank holidays
        deadruns = txc.timetable_from_filename(FIXTURES_DIR, 'SVRLABO024A.xml', date(2017, 4, 14))
        self.assertEqual(7, len(deadruns.groupings[0].rows[0].times))

    def test_timetable_servicedorg(self):
        """Test a timetable with a ServicedOrganisation"""
        timetable_during_holiday = txc.timetable_from_filename(FIXTURES_DIR, 'swe_31-668-_-y10-1.xml',
                                                               date(2016, 8, 31))
        self.assertEqual([], timetable_during_holiday.groupings[0].rows[0].times)

        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'swe_31-668-_-y10-1.xml', date(2016, 9, 10))
        self.assertEqual([time(8, 2)], timetable.groupings[0].rows[0].times)

    def test_timetable_welsh_servicedorg(self):
        """Test a timetable from Wales (with SequenceNumbers on Journeys),
        with a university ServicedOrganisation
        """
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'CGAO305.xml', date(2017, 1, 23))
        self.assertEqual(0, len(timetable.groupings[0].rows[0].times))

        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'CGAO305.xml', None)
        self.assertEqual(3, len(timetable.groupings[0].rows[0].times))

    def test_timetable_holidays_only(self):
        """Test a service with a HolidaysOnly operating profile
        """
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'twm_6-14B-_-y11-1.xml', date(2017, 1, 23))
        self.assertEqual(0, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(0, len(timetable.groupings[1].rows[0].times))

        # Has some journeys that operate on 1 May 2017
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'twm_6-14B-_-y11-1.xml', date(2017, 5, 1))
        self.assertEqual(8, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(7, len(timetable.groupings[1].rows[0].times))

    def test_timetable_goole(self):
        # outside of operating period
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'SVRYEAGT00.xml', date(2007, 6, 27))
        self.assertFalse(hasattr(timetable, 'groupings'))
        self.assertEqual('', timetable.mode)

        # during a DaysOfNonOperation
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'SVRYEAGT00.xml', date(2012, 6, 27))
        self.assertEqual([], timetable.groupings[0].rows[0].times)

        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'SVRYEAGT00.xml', date(2017, 1, 27))
        self.assertEqual(timetable.groupings[0].rows[0].times, ['', '', time(9, 48), time(10, 28), time(11, 8),
                                                                time(11, 48), time(12, 28), time(13, 8), time(13, 48),
                                                                time(14, 28), time(15, 8), '', ''])

        with freeze_time('21 Feb 2016'):
            date_options = list(timetable.date_options())
            self.assertEqual(date_options[0]['date'], date(2016, 2, 21))
            self.assertEqual(date_options[-1]['date'], date(2017, 1, 27))

    def test_timetable_cardiff_airport(self):
        """Should be able to distinguish between Cardiff and Cardiff Airport as start and end of a route"""
        timetable = txc.timetable_from_filename(FIXTURES_DIR, 'TCAT009.xml', None)
        self.assertEqual(str(timetable.groupings[0]), 'Cardiff Airport - Cardiff  ')
        self.assertEqual(str(timetable.groupings[1]), 'Cardiff   - Cardiff Airport')


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


class VehicleJourneyTest(TestCase):
    def test_special_cases(self):
        journey = txc.VehicleJourney(ET.fromstring("""
            <VehicleJourney xmlns="http://www.transxchange.org.uk/">
                <PrivateCode>em-11-X52-_-y08-1-2-T0</PrivateCode>
                <OperatingProfile>
                    <RegularDayType>
                        <DaysOfWeek>
                            <MondayToFriday />
                        </DaysOfWeek>
                    </RegularDayType>
                    <BankHolidayOperation>
                        <DaysOfNonOperation>
                            <GoodFriday />
                            <MayDay />
                            <EasterMonday />
                            <SpringBank />
                        </DaysOfNonOperation>
                    </BankHolidayOperation>
                </OperatingProfile>
                <VehicleJourneyCode>VJ_11-X52-_-y08-1-2-T0</VehicleJourneyCode>
                <ServiceRef>11-X52-_-y08-1</ServiceRef>
                <LineRef>11-X52-_-y08-1</LineRef>
                <JourneyPatternRef>JP_11-X52-_-y08-1-2-H-2</JourneyPatternRef>
                <DepartureTime>09:15:00</DepartureTime>
            </VehicleJourney>
        """), {'JP_11-X52-_-y08-1-2-H-2': None}, {}, None)

        self.assertFalse(journey.should_show(date(2017, 2, 20)))
        self.assertTrue(journey.should_show(date(2017, 3, 28)))

        self.assertTrue(journey.should_show(date(2017, 4, 13)))
        self.assertFalse(journey.should_show(date(2017, 4, 14)))  # Good Friday
        self.assertFalse(journey.should_show(date(2017, 4, 15)))
        self.assertFalse(journey.should_show(date(2017, 4, 16)))
        self.assertFalse(journey.should_show(date(2017, 4, 17)))  # Easter Monday
        self.assertTrue(journey.should_show(date(2017, 4, 18)))

        # first Wednesday of the month
        journey.code = 'VJ_21-NS1-A-y08-1-2-T0'
        self.assertTrue(journey.should_show(date(2017, 1, 4)))
        self.assertFalse(journey.should_show(date(2017, 1, 11)))
        self.assertFalse(journey.should_show(date(2017, 1, 18)))
        self.assertTrue(journey.should_show(date(2017, 2, 1)))
        self.assertFalse(journey.should_show(date(2017, 3, 15)))

        # second Wednesday of the month
        journey.code = 'VJ_21-WRO-X-y08-1-2-T0'
        self.assertFalse(journey.should_show(date(2017, 1, 4)))
        self.assertTrue(journey.should_show(date(2017, 1, 11)))
        self.assertFalse(journey.should_show(date(2017, 1, 18)))
        self.assertFalse(journey.should_show(date(2017, 1, 25)))

        # third Wednesday of the month
        journey.code = 'VJ_21-NS2-A-y08-1-2-T0'
        self.assertFalse(journey.should_show(date(2017, 1, 4)))
        self.assertFalse(journey.should_show(date(2017, 1, 11)))
        self.assertTrue(journey.should_show(date(2017, 1, 18)))
        self.assertFalse(journey.should_show(date(2017, 1, 25)))


class OperatingProfileTest(TestCase):
    def test_bank_holidays(self):
        operating_profile = txc.OperatingProfile(ET.fromstring("""
            <OperatingProfile xmlns="http://www.transxchange.org.uk/">
                <RegularDayType>
                    <DaysOfWeek>
                        <MondayToSunday />
                      </DaysOfWeek>
                    </RegularDayType>
                    <SpecialDaysOperation>
                    <DaysOfNonOperation>
                        <DateRange>
                            <StartDate>2017-04-17</StartDate>
                            <EndDate>2017-04-17</EndDate>
                            <Note>QE Line</Note>
                        </DateRange>
                    </DaysOfNonOperation>
                </SpecialDaysOperation>
            </OperatingProfile>
        """), {})
        self.assertTrue(operating_profile.should_show(date(2017, 4, 14)))  # Good Friday
        self.assertFalse(operating_profile.should_show(date(2017, 4, 17)))

        operating_profile = txc.OperatingProfile(ET.fromstring("""
            <OperatingProfile xmlns="http://www.transxchange.org.uk/">
                <RegularDayType>
                    <HolidaysOnly />
                </RegularDayType>
                <BankHolidayOperation>
                    <DaysOfOperation>
                        <EasterMonday />
                    </DaysOfOperation>
                    <DaysOfNonOperation />
                </BankHolidayOperation>
            </OperatingProfile>
        """), {})
        self.assertFalse(operating_profile.should_show(date(2017, 4, 14)))  # Good Friday
        self.assertTrue(operating_profile.should_show(date(2017, 4, 17)))  # Easter Monday

        operating_profile = txc.OperatingProfile(ET.fromstring("""
            <OperatingProfile xmlns="http://www.transxchange.org.uk/">
                <RegularDayType>
                    <HolidaysOnly />
                </RegularDayType>
                <BankHolidayOperation>
                    <DaysOfOperation>
                        <GoodFriday />
                    </DaysOfOperation>
                    <DaysOfNonOperation />
                </BankHolidayOperation>
            </OperatingProfile>
        """), {})
        self.assertFalse(operating_profile.should_show(date(2017, 4, 10)))
        self.assertFalse(operating_profile.should_show(date(2017, 4, 13)))
        self.assertTrue(operating_profile.should_show(date(2017, 4, 14)))  # Good Friday
        self.assertFalse(operating_profile.should_show(date(2017, 4, 17)))  # Easter Monday
        self.assertFalse(operating_profile.should_show(date(2017, 4, 18)))

        operating_profile = txc.OperatingProfile(ET.fromstring("""
            <OperatingProfile xmlns="http://www.transxchange.org.uk/">
                <RegularDayType>
                    <HolidaysOnly />
                </RegularDayType>
                <SpecialDaysOperation>
                    <DaysOfOperation>
                        <DateRange>
                            <StartDate>2017-04-17</StartDate>
                            <EndDate>2017-04-17</EndDate>
                            <Note>EasterMonday</Note>
                        </DateRange>
                    </DaysOfOperation>
                    <DaysOfNonOperation>
                        <DateRange>
                            <StartDate>2017-04-14</StartDate>
                            <EndDate>2017-04-14</EndDate>
                            <Note>GoodFriday</Note>
                        </DateRange>
                    </DaysOfNonOperation>
                </SpecialDaysOperation>
            </OperatingProfile>
        """), {})
        self.assertFalse(operating_profile.should_show(date(2017, 4, 10)))
        self.assertFalse(operating_profile.should_show(date(2017, 4, 13)))
        self.assertFalse(operating_profile.should_show(date(2017, 4, 14)))  # Good Friday
        self.assertTrue(operating_profile.should_show(date(2017, 4, 17)))  # Easter Monday
        self.assertFalse(operating_profile.should_show(date(2017, 4, 18)))

    def test_days_of_week(self):
        operating_profile = txc.OperatingProfile(ET.fromstring("""
            <OperatingProfile xmlns="http://www.transxchange.org.uk/">
                <RegularDayType>
                  <DaysOfWeek>
                    <Weekend />
                  </DaysOfWeek>
                </RegularDayType>
              </OperatingProfile>
        """), {})
        self.assertEqual('Saturday to Sunday', str(operating_profile))
        self.assertFalse(operating_profile.should_show(date(2017, 4, 10)))
        self.assertFalse(operating_profile.should_show(date(2017, 4, 14)))
        self.assertTrue(operating_profile.should_show(date(2017, 4, 15)))
        self.assertTrue(operating_profile.should_show(date(2017, 4, 16)))
        self.assertFalse(operating_profile.should_show(date(2017, 4, 17)))
