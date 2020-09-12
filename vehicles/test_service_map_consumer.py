import vcr
from freezegun import freeze_time
from channels.testing import WebsocketCommunicator
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.utils import timezone
from busstops.models import Region, Service, ServiceCode, StopPoint, DataSource, SIRISource, Operator
from bustimes.models import Route, Calendar, Trip
from buses.routing import application
from .siri_one_shot import siri_one_shot


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class WebsocketConsumerTest(TestCase):
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

    async def test_service_map_consumer(self):
        with vcr.use_cassette('data/vcr/icarus.yaml'):
            with freeze_time('2019-06-08'):
                url = f"/ws/vehicle_positions/services/{self.service.id}"
                communicator = WebsocketCommunicator(application, url)
                connected, subprotocol = await communicator.connect()
                self.assertTrue(connected)

                message = await communicator.receive_json_from()
                self.assertEqual(message, [])

    def test_siri_one_shot(self):
        # url = f'/vehicles.json?service={self.service.id}'

        with vcr.use_cassette('data/vcr/icarus.yaml'):
            with freeze_time('2019-06-08'):
                now = timezone.now()

                with self.assertNumQueries(2):
                    self.assertEqual('nothing scheduled', siri_one_shot(self.code_1, now, False))
                with self.assertNumQueries(1):
                    self.assertEqual('cached (nothing scheduled)', siri_one_shot(self.code_1, now, False))

                self.assertEqual('nothing scheduled', cache.get(f'{self.service.id}:Icarus'))

            with freeze_time('2019-06-08 20:37+01:00'):
                now = timezone.now()

                with self.assertNumQueries(49):
                    self.assertIsNone(siri_one_shot(self.code_1, now, True))
                with self.assertNumQueries(1):
                    self.assertEqual('cached (line name)', siri_one_shot(self.code_1, now, True))

                key = 'http://data.icarus.cloudamber.com/StopMonitoringRequest.ashx:torbaydevon_siri_traveline:FLCN'
                self.assertEqual('line name', cache.get(key))
