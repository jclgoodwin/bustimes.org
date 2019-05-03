import socketio
from ciso8601 import parse_datetime
from django.db.transaction import atomic
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from busstops.models import DataSource
from ...models import Vehicle, VehicleJourney, VehicleLocation


sio = socketio.Client()
source = None
globalism = {}


@sio.on('connect')
def on_connect():
    print('connection established')


@sio.on('posUpdate')
@atomic
def on_message(data):
    print(data)
    vehicle, created = Vehicle.objects.get_or_create(operator_id='MSOT', code=data['ass'])
    datetime = parse_datetime(data['date'])
    service = data['extra'].get('custR', '')
    if created or not vehicle.latest_location or vehicle.latest_location.journey.route_name != service:
        journey = VehicleJourney.objects.create(
            vehicle=vehicle,
            datetime=datetime,
            source=globalism['source'],
            route_name=service
        ).id
    else:
        vehicle.latest_location.journey.vehiclelocation_set.update(current=False)
        journey = vehicle.latest_location.journey_id
    vehicle.latest_location = VehicleLocation.objects.create(
        journey_id=journey,
        datetime=datetime,
        latlong=Point(data['lng'], data['lat']),
        heading=data['dir'],
        current=True
    )
    vehicle.save()


@sio.on('disconnect')
def on_disconnect():
    print('disconnected from server')


class Command(BaseCommand):
    def handle(self, *args, **options):
        globalism['source'] = DataSource.objects.get_or_create(name='Marshalls')[0]

        sio.connect('https://nodejs.bigchangeapps.com', {
            'Origin': 'https://map.bigchangeapps.com',
            'Referer': 'https://map.bigchangeapps.com/',
        }, socketio_path='/map/socket.io')
        sio.emit('startListening', {'custUid': 'a52b9550-ceed', 'byAsset': True})
