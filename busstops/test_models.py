from django.test import TestCase
from bustimes.models import Route
from .models import (
    Region, AdminArea, DataSource, District, Locality, Operator, Service, StopPoint
)
from .admin import OperatorAdmin


class RegionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create some regions
        cls.midlands = Region.objects.create(pk='NM', name='North Midlands')
        cls.east = Region.objects.create(pk='ME', name='Middle East')
        cls.ireland = Region.objects.create(pk='IE', name='Ireland')

    def test_string(self):
        self.assertEqual(str(self.midlands), 'North Midlands')

    def test_the(self):
        "Regions with certain names should have 'the' prepended, and others shouldn't."
        self.assertEqual(self.midlands.the(), 'the North Midlands')
        self.assertEqual(self.east.the(), 'the Middle East')
        self.assertEqual(self.ireland.the(), 'Ireland')

    def test_get_absolute_url(self):
        self.assertEqual(self.midlands.get_absolute_url(), '/regions/NM')


class LocalityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.midlands = Region.objects.create(pk='NM', name='North Midlands')
        cls.dorset = AdminArea.objects.create(pk='4', atco_code=2, region=cls.midlands, name='Dorset')

        cls.north_yorkshire = District.objects.create(pk='2', admin_area=cls.dorset, name='North Yorkshire')

        cls.brinton = Locality.objects.create(pk='1', admin_area=cls.dorset, name='Brinton')
        cls.york = Locality.objects.create(pk='2', admin_area=cls.dorset, name='York', qualifier_name='York')

    def test_get_qualified_name(self):
        self.assertEqual(self.brinton.get_qualified_name(), 'Brinton')
        self.assertEqual(self.york.get_qualified_name(), 'York, York')

    def test_string(self):
        self.assertEqual(str(self.brinton), 'Brinton')
        self.assertEqual(str(self.york), 'York')

        self.assertEqual(str(self.brinton.admin_area), 'Dorset')


class OperatorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(pk='N', name='North')
        cls.chariots = Operator.objects.create(pk='CHAR', region=cls.north,
                                               name='Ainsley\'s Chariots')

    def test_get_qualified_name(self):
        self.assertEqual(str(self.chariots), 'Ainsley\'s Chariots')

    def test_admin(self):
        admin = OperatorAdmin(Operator, None)
        operators = admin.get_queryset(None)
        self.assertEqual(len(operators), 1)
        self.assertEqual(admin.service_count(operators[0]), 0)
        self.assertEqual(admin.operator_codes(operators[0]), '')


class ServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(id='L', name='London')
        cls.london_service = Service.objects.create(
            service_code='tfl_8-N41-_-y05', line_name='N41',
            date='2000-1-1', region_id='L'
        )
        source = DataSource.objects.create(name='EA')
        cls.service = Service.objects.create(service_code='ea_21-1A-_-y08', source=source, region=cls.region,
                                             date='2018-01-01')
        Route.objects.create(code='ea_21-1A-_-y08-2.xml', service=cls.service, start_date='2012-05-01', source=source)
        Route.objects.create(code='ea_21-1A-_-y08-1.xml', service=cls.service, start_date='2012-01-01', source=source)

    def test_str(self):
        self.assertEqual(str(self.london_service), 'N41')

        self.london_service.line_name = ''
        self.assertEqual(str(self.london_service), 'tfl_8-N41-_-y05')
        self.london_service.line_name = 'N41'

        service = Service(line_name='C', description='Coasthopper - Filey')
        self.assertEqual(str(service), 'C - Coasthopper - Filey')

        service.line_name = 'Coast Hopper'
        service.description = 'Coast Hopper'
        self.assertEqual(str(service), 'Coast Hopper')

        service.line_name = 'Coast Hopper'
        service.description = 'Coast Hopper – Brighton - Filey'
        self.assertEqual(str(service), 'Coast Hopper – Brighton - Filey')

    def test_get_a_mode(self):
        self.assertEqual(self.london_service.get_a_mode(), 'A ')

        self.london_service.mode = 'Underground'
        self.assertEqual(self.london_service.get_a_mode(), 'An Underground')

    def test_traveline_links(self):
        source = DataSource.objects.create(name='Y')
        # this will cause an IndexError that needs to be caught
        Route.objects.create(service=self.london_service, source=source,
                             code='swindonbus_1587119026.zip/Swindon-17042020_SER14.xml')

        self.assertEqual([], list(self.london_service.get_traveline_links()))

        links = list(self.service.get_traveline_links())
        self.assertEqual(links, [
            ('http://nationaljourneyplanner.travelinesw.com/swe-ttb/XSLT_TTB_REQUEST?line=2101A&lineVer=1'
                '&net=ea&project=y08&command=direct&outputFormat=0', 'Timetable on the Traveline website'),
            ('http://nationaljourneyplanner.travelinesw.com/swe-ttb/XSLT_TTB_REQUEST?line=2101A&lineVer=2'
                '&net=ea&project=y08&command=direct&outputFormat=0', 'Timetable from 1 May on the Traveline website'),
            ])

    def test_get_operator_number(self):
        self.assertIsNone(self.london_service.get_operator_number('MGBD'))

        self.assertEqual('11', self.london_service.get_operator_number('MEGA'))
        self.assertEqual('11', self.london_service.get_operator_number('MBGD'))

        self.assertEqual('12', self.london_service.get_operator_number('NATX'))
        self.assertEqual('12', self.london_service.get_operator_number('NXSH'))
        self.assertEqual('12', self.london_service.get_operator_number('NXAP'))

        self.assertEqual('41', self.london_service.get_operator_number('BHAT'))
        self.assertEqual('53', self.london_service.get_operator_number('ESYB'))
        self.assertEqual('20', self.london_service.get_operator_number('WAIR'))
        self.assertEqual('18', self.london_service.get_operator_number('TVSN'))


class StopPointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiff_airport_locality = Locality(name='Cardiff Airport')
        cls.cardiff_airport_stop = StopPoint(common_name='Airport', locality=cls.cardiff_airport_locality)
        cls.ballyblack_church = StopPoint.objects.create(atco_code='700000002498', locality_centre=False, active=True,
                                                         common_name='Ballyblack Church', town='Ballyblack')

    def test_get_qualified_name(self):
        self.assertEqual('Ballyblack Church', self.ballyblack_church.get_qualified_name())
        self.ballyblack_church.common_name = 'Methodist Church'
        self.assertEqual('Ballyblack Methodist Church', self.ballyblack_church.get_qualified_name())

        self.assertEqual('Cardiff Airport', self.cardiff_airport_stop.get_qualified_name())
        self.cardiff_airport_stop.indicator = 'Stop M'
        self.assertEqual('Cardiff Airport (Stop M)', self.cardiff_airport_stop.get_qualified_name())
