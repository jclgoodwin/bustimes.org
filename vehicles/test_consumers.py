import pytest
from freezegun import freeze_time
from django.contrib.gis.geos import Point
from channels.testing import WebsocketCommunicator
from busstops.models import DataSource
from .consumers import VehicleMapConsumer
from .models import Vehicle, VehicleJourney, VehicleLocation


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        source = DataSource.objects.create(name='Source')
        vehicle = Vehicle.objects.create(code='SA60 TWP')
        journey = VehicleJourney.objects.create(route_name='69', vehicle=vehicle, source=source,
                                                datetime='2018-12-25 19:47+00:00')
        vehicle.latest_location = VehicleLocation.objects.create(current=True, journey=journey,
                                                                 latlong=Point(1.3, 52.64),
                                                                 datetime=journey.datetime)
        vehicle.save(update_fields=['latest_location'])


@pytest.mark.asyncio
@pytest.mark.django_db
@freeze_time('2018-12-25 19:47+00:00')
async def test_my_consumer():

    communicator = WebsocketCommunicator(VehicleMapConsumer, "/ws/vehicle_positions")
    connected, subprotocol = await communicator.connect()
    assert connected

    await communicator.send_json_to(
        [1.2105560302734377, 52.63129172228801, 1.4577484130859377, 52.66524398541177]
    )
    message = await communicator.receive_json_from()
    assert len(message) == 1
    message = message[0]
    assert message['c'] is None
    assert message['h'] is None
    assert message['l'] == [1.3, 52.64]

    await communicator.send_json_to(
        [1.2105560302734377, 50.63129172228801, 1.4577484130859377, 52.66524398541177]
    )

    await communicator.send_input({
        'type': 'move_vehicle',
        'id': 13,
        'datetime': '3',
        'latlong': (1.31, 52.644),
        'heading': 2,
        'route': '33',
        'css': '',
        'text_colour': '',
        'early': -1
    })
    message_b = await communicator.receive_json_from()
    assert message_b == [
        {'i': 13, 'd': '3', 'l': [1.31, 52.644], 'h': 2, 'r': '33', 'c': '', 't': '', 'e': -1}
    ]
    await communicator.receive_nothing()
    await communicator.disconnect()
