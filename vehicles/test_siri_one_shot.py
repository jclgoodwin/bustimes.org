import vcr
from freezegun import freeze_time
from django.core.cache import cache
from django.test import TestCase, override_settings
from busstops.models import (Region, Service, ServiceCode, StopPoint, DataSource, SIRISource, Journey, StopUsageUsage,
                             Operator)


class SIRIOneShotTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(name='Icarus')

        destination = StopPoint.objects.create(common_name='Plymouth Aerodrome', active=True)
        region = Region.objects.create(id='SW', name='South West')
        operator = Operator.objects.create(id='SDVN', region=region, name='Stagecoach Devonshire')
        service = Service.objects.create(service_code='swe_33-FLC-_-y10', date='2019-06-08')
        service.operator.add(operator)
        journey = Journey.objects.create(service=service, datetime='2019-06-08 20:36+01:00', destination=destination)
        StopUsageUsage.objects.create(journey=journey, datetime='2019-06-08 20:38+01:00', stop=destination, order=0)

        cls.code_1 = ServiceCode.objects.create(service=service, code='FLCN', scheme='Devon SIRI')
        cls.code_2 = ServiceCode.objects.create(service=service, code='FLC', scheme='Bucks SIRI')
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

            with freeze_time('2019-06-08'):
                with self.assertNumQueries(7):
                    self.client.get('/vehicles.json?service=swe_33-FLC-_-y10')

                self.assertEqual('nothing scheduled', cache.get('swe_33-FLC-_-y10:Icarus'))

            with freeze_time('2019-06-08 20:37+01:00'):
                with self.assertNumQueries(48):
                    self.client.get('/vehicles.json?service=swe_33-FLC-_-y10')
                with self.assertNumQueries(6):
                    res = self.client.get('/vehicles.json?service=swe_33-FLC-_-y10')

                key = 'http://data.icarus.cloudamber.com/StopMonitoringRequest.ashx:torbaydevon_siri_traveline:FLCN'
                self.assertEqual('line name', cache.get(key))

        json = res.json()

        self.assertEqual(len(json['features']), 4)
