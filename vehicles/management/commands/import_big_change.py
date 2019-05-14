import socketio
from ciso8601 import parse_datetime
from django.db.transaction import atomic
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from busstops.models import DataSource, Service
from ...models import Vehicle, VehicleJourney, VehicleLocation


sio = socketio.Client()
source = None
globalism = {}


@sio.on('connect')
def on_connect():
    print('connection established')


@sio.on('posUpdate')
def on_message(data):
    print(data)
    vehicle, created = Vehicle.objects.get_or_create(operator_id='MSOT', code=data['ass'])
    datetime = parse_datetime(data['date'])
    latlong = Point(data['lng'], data['lat'])

    journey = None
    service = None

    if not created:
        latest_location = vehicle.latest_location
        current = latest_location and (datetime - latest_location.datetime).total_seconds() < 180
        if current and latest_location.journey.service:
            if latest_location.journey.service.geometry.envelope.covers(latlong):
                journey = latest_location.journey

        if not journey:
            try:
                service = Service.objects.filter(
                    operator='MSOT',
                    journey__datetime__lte=datetime,
                    journey__stopusageusage__datetime__gte=datetime,
                    geometry__bboverlaps=latlong
                ).distinct().get()
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                pass

        if current and not service and not latest_location.journey.service:
            journey = latest_location.journey

    if not journey:
        journey = VehicleJourney.objects.create(
            vehicle=vehicle,
            datetime=datetime,
            source=globalism['source'],
            service=service,
            route_name=data['extra'].get('custR', '')
        )

    with atomic():
        if not created and latest_location:
            latest_location.journey.vehiclelocation_set.update(current=False)
        vehicle.latest_location = VehicleLocation.objects.create(
            journey=journey,
            datetime=datetime,
            latlong=latlong,
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
