import asyncio
import websockets
import ciso8601
import json
from datetime import timedelta
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from busstops.models import Operator, Service, DataSource
from ...models import Vehicle, VehicleJourney, VehicleLocation


class Command(BaseCommand):
    @transaction.atomic
    def handle_siri_vm_vehicle(self, item):
        operator = item['OperatorRef']
        operator = {
            'WP': 'WHIP',
            'GP': 'GPLM',
            'CBLE': 'CBBH',
            'ATS': 'ARBB'
        }.get(operator, operator)
        if operator == 'UNIB':
            return
        try:
            operator = Operator.objects.get(pk=operator)
        except Operator.DoesNotExist as e:
            print(e, operator, item)
            return
        if operator.pk == 'SCCM':
            service = Service.objects.filter(operator__in=('SCCM', 'SCPB', 'SCHU', 'SCBD'))
        else:
            service = operator.service_set
        service = service.filter(current=True)
        line_name = item['PublishedLineName']
        if line_name.startswith('PR'):
            service = service.filter(pk__contains='-{}-'.format(line_name))
        else:
            if operator.pk == 'WHIP' and line_name == 'U':
                line_name = 'Universal U'
            service = service.filter(line_name=line_name)
        try:
            try:
                service = service.get()
            except Service.MultipleObjectsReturned:
                service = service.filter(Q(stops=item['OriginRef']) | Q(stops=item['DestinationRef'])).distinct().get()
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            print(e, operator.pk, line_name)
            service = None
        vehicle, created = Vehicle.objects.get_or_create(operator=operator, code=item['VehicleRef'], source=self.source)
        journey = None
        if not created and vehicle.latest_location and vehicle.latest_location.current:
            vehicle.latest_location.current = False
            vehicle.latest_location.save()
            if vehicle.latest_location.journey.service == service:
                journey = vehicle.latest_location.journey
        if not journey or journey.code != item['DatedVehicleJourneyRef']:
            journey = VehicleJourney.objects.create(
                vehicle=vehicle,
                service=service,
                source=self.source,
                datetime=ciso8601.parse_datetime(item['OriginAimedDepartureTime']),
                destination=item['DestinationName'],
                code=item['DatedVehicleJourneyRef']
            )
        vehicle.latest_location = VehicleLocation.objects.create(
            journey=journey,
            datetime=ciso8601.parse_datetime(item['RecordedAtTime']),
            latlong=Point(float(item['Longitude']), float(item['Latitude'])),
            heading=item['Bearing'],
            current=True
        )
        vehicle.save()

    def handle_data(self, data):
        for item in data['request_data']:
            self.handle_siri_vm_vehicle(item)

        now = timezone.now()
        self.source.datetime = now
        self.source.save()

        five_minutes_ago = now - timedelta(minutes=5)
        locations = VehicleLocation.objects.filter(journey__source=self.source, current=True)
        locations.filter(datetime__lte=five_minutes_ago).update(current=False)

    async def sock_it(self):
        async with websockets.connect(self.source.url) as websocket:
            await websocket.send('{ "msg_type": "rt_connect" }')

            response = await websocket.recv()

            assert response.decode() == '{ "msg_type": "rt_connect_ok" }'

            await websocket.send('{ "msg_type": "rt_subscribe", "request_id": "A" }')

            while True:
                response = await websocket.recv()
                self.handle_data(json.loads(response))

    def handle(self, *args, **options):
        self.source = DataSource.objects.get(name='cambridge')

        while True:
            try:
                asyncio.get_event_loop().run_until_complete(self.sock_it())
            except websockets.exceptions.ConnectionClosed as e:
                print(e)
