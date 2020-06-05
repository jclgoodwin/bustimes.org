import vcr
from freezegun import freeze_time
from django.core.cache import cache
from django.test import TestCase, override_settings
from busstops.models import Region, Service, ServiceCode, StopPoint, DataSource, SIRISource, Operator
from bustimes.models import Route, Calendar, Trip


class SIRIOneShotTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='Icarus')

        destination = StopPoint.objects.create(common_name='Plymouth Aerodrome', active=True)
        region = Region.objects.create(id='SW', name='South West')
        operator = Operator.objects.create(id='SDVN', region=region, name='Stagecoach Devonshire')
        cls.service = Service.objects.create(service_code='swe_33-FLC-_-y10', date='2019-06-08')
        cls.service.operator.add(operator)
        route = Route.objects.create(service=cls.service, source=source)
        calendar = Calendar.objects.create(start_date='2019-06-08', mon=True, tue=True, wed=True, thu=True, fri=True,
                                           sat=True, sun=True)
        Trip.objects.create(route=route, start='20:40', end='20:50', calendar=calendar, destination=destination)

        cls.code_1 = ServiceCode.objects.create(service=cls.service, code='FLCN', scheme='Devon SIRI')
        cls.code_2 = ServiceCode.objects.create(service=cls.service, code='FLC', scheme='Bucks SIRI')
        cls.siri_source = SIRISource.objects.create(name='Devon', requestor_ref='torbaydevon_siri_traveline',
                                                    url='http://data.icarus.cloudamber.com/StopMonitoringRequest.ashx')

    def test_service_codes(self):
        self.assertEqual('Devon SIRI FLCN', str(self.code_1))
        self.assertEqual('Bucks SIRI FLC', str(self.code_2))

    def test_siri_source(self):
        self.assertEqual('Devon', str(self.siri_source))

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_vehicles_json(self):
        with vcr.use_cassette('data/vcr/icarus.yaml'):

            url = '/vehicles.json?service=swe_33-FLC-_-y10'

            with freeze_time('2019-06-08'):
                with self.assertNumQueries(6):
                    self.client.get(url)
                self.assertEqual('nothing scheduled', cache.get(f'{self.service.id}:Icarus'))

            with freeze_time('2019-06-08 20:37+01:00'):
                with self.assertNumQueries(49):
                    self.client.get(url)
                with self.assertNumQueries(2):
                    res = self.client.get(url)

                key = 'http://data.icarus.cloudamber.com/StopMonitoringRequest.ashx:torbaydevon_siri_traveline:FLCN'
                self.assertEqual('line name', cache.get(key))

        json = res.json()

        self.assertEqual(len(json['features']), 4)
