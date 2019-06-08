import vcr
from freezegun import freeze_time
from django.test import TestCase
from busstops.models import (Region, Service, ServiceCode, StopPoint, DataSource, SIRISource, Journey, StopUsageUsage,
                             Operator)
# from .models import Vehicle, VehicleJourney, VehicleLocation


@freeze_time('2019-06-08 20:37+01:00')
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

        ServiceCode.objects.get_or_create(service=service, code='FLCN', scheme='Devon SIRI')
        ServiceCode.objects.get_or_create(service=service, code='FLC', scheme='Bucks SIRI')
        SIRISource.objects.get_or_create(name='Devon', requestor_ref='torbaydevon_siri_traveline',
                                         url='http://data.icarus.cloudamber.com/StopMonitoringRequest.ashx')

    def test_vehicles_json(self):
        with vcr.use_cassette('data/vcr/icarus.yaml'):
            res = self.client.get('/vehicles.json?service=swe_33-FLC-_-y10')

        json = res.json()

        self.assertEqual(len(json['features']), 4
