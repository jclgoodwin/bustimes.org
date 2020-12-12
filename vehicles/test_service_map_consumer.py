from channels.testing import WebsocketCommunicator
from django.test import TestCase, override_settings
from busstops.models import Region, Service, Operator
from vehicles.routing import application


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class WebsocketConsumerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='SW', name='South West')
        operator = Operator.objects.create(id='SDVN', region=region, name='Stagecoach Devonshire')
        cls.service = Service.objects.create(service_code='swe_33-FLC-_-y10', date='2019-06-08')
        cls.service.operator.add(operator)

    async def test_service_map_consumer(self):
        url = f"/ws/vehicle_positions/services/{self.service.id}"
        communicator = WebsocketCommunicator(application, url)
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        message = await communicator.receive_json_from()
        self.assertEqual(message, [])

        self.assertTrue(await communicator.receive_nothing())
