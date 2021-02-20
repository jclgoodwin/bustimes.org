from channels.testing import WebsocketCommunicator
from django.contrib.gis.geos import Point
from django.test import TestCase
from busstops.models import Region, Service, Operator, DataSource
from .routing import application
from .consumers import VehicleMapConsumer
from .models import Vehicle, VehicleJourney, VehicleLocation


class WebsocketConsumerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='SW', name='South West')
        operator = Operator.objects.create(id='SDVN', region=region, name='Stagecoach Devonshire')
        cls.service = Service.objects.create(service_code='swe_33-FLC-_-y10', date='2019-06-08')
        cls.service.operator.add(operator)

        source = DataSource.objects.create(name='Source')
        vehicle = Vehicle.objects.create(code='SA60 TWP')
        journey = VehicleJourney.objects.create(route_name='69', vehicle=vehicle, source=source,
                                                datetime='2018-12-25 19:47+00:00')
        vehicle.latest_location = VehicleLocation.objects.create(current=True, journey=journey,
                                                                 latlong=Point(1.3, 52.64),
                                                                 datetime=journey.datetime)
        vehicle.save(update_fields=['latest_location'])

    async def test_service_map_consumer(self):
        url = f"/ws/vehicle_positions/services/{self.service.id}"
        communicator = WebsocketCommunicator(application, url)
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        message = await communicator.receive_json_from()
        self.assertEqual(message, [])

        self.assertTrue(await communicator.receive_nothing())

    async def test_big_map(self):
        communicator = WebsocketCommunicator(VehicleMapConsumer.as_asgi(), "/ws/vehicle_positions")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to([1, 50, 2, 55])
        await communicator.receive_nothing()

        items = [{'i': 13, 'd': '3', 'l': [1.31, 52.644], 'h': 2, 'r': '33', 'c': '', 't': '', 'e': -1}]

        await communicator.send_input({'type': 'move_vehicles', 'items': items})
        message_b = await communicator.receive_json_from()
        self.assertEqual(items, message_b)

        await communicator.receive_nothing()
        await communicator.disconnect()
