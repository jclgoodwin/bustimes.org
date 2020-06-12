import asyncio
import websockets
import ciso8601
import json
import html
import pyppeteer
from asgiref.sync import sync_to_async
from datetime import timedelta
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import Error
from django.db.models import Q
from django.utils import timezone, dateparse
from busstops.models import Operator, Service, DataSource, Locality
from ...models import Vehicle, VehicleJourney, VehicleLocation


class Command(BaseCommand):
    operators = {}
    vehicles = Vehicle.objects.select_related('latest_location__journey__service')

    def get_operator(self, ref):
        if ref in self.operators:
            return self.operators[ref]
        try:
            try:
                operator = Operator.objects.get(operatorcode__code=ref, operatorcode__source=self.source)
            except Operator.DoesNotExist:
                operator = Operator.objects.get(pk=ref)
        except Operator.DoesNotExist as e:
            print(e, ref)
            return
        self.operators[ref] = operator
        return operator

    def get_vehicle(self, operator, item):
        vehicle = item['VehicleRef']
        if vehicle.startswith(item['OperatorRef'] + '-'):
            vehicle = vehicle[len(item['OperatorRef']) + 1:]
        defaults = {
            'source': self.source
        }
        if vehicle.isdigit():
            if item['OperatorRef'] == 'ATS' or item['OperatorRef'] == 'ASC':
                defaults['code'] = vehicle
                return self.vehicles.get_or_create(defaults, operator=operator, fleet_number=vehicle)
            defaults = {'fleet_number': vehicle}
        if type(operator) is Operator:
            return self.vehicles.get_or_create(defaults, operator=operator, code=vehicle)
        defaults = {'operator_id': operator[0]}
        if operator[0] == 'SCCM':
            return self.vehicles.get_or_create(defaults, operator__name__startswith='Stagecoach ', code=vehicle)
        return self.vehicles.get_or_create(defaults, operator__in=operator, code=vehicle)

    def get_service(self, operator, item):
        line_name = item['PublishedLineName']

        if type(operator) is Operator:
            service = operator.service_set
            if operator.pk == 'WHIP' and line_name == 'U':
                line_name = 'Universal U'
        else:
            service = Service.objects.filter(operator__in=operator)
        service = service.filter(current=True, line_name=line_name)

        try:
            try:
                return service.get()
            except Service.MultipleObjectsReturned:
                try:
                     return service.filter(Q(stops=item['OriginRef']) | Q(stops=item['DestinationRef'])).distinct().get()
                except Service.MultipleObjectsReturned:
                     return service.filter(stops=item['OriginRef']).filter(stops=item['DestinationRef']).distinct().get()
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            if line_name != 'Tour':
                print(e, item)

    def handle_siri_vm_vehicle(self, item):
        operator = self.get_operator(item['OperatorRef'])
        if not operator:
            return
        operator_options = None
        if operator.pk == 'SCCM':
            operator_options = ('SCCM', 'SCPB', 'SCHU', 'SCBD')
        elif operator.pk == 'CBBH':
            operator_options = ('CBBH', 'CBNL')

        vehicle, created = self.get_vehicle(operator_options or operator, item)

        journey = None

        line_name = item['PublishedLineName']
        journey_code = item['DatedVehicleJourneyRef']
        departure_time = ciso8601.parse_datetime(item['OriginAimedDepartureTime'])
        if not created and vehicle.latest_location:
            location = vehicle.latest_location
            latest_journey = location.journey
            if line_name == latest_journey.route_name and journey_code == latest_journey.code:
                if departure_time == latest_journey.datetime:
                    journey = latest_journey
        else:
            location = VehicleLocation()

        if not journey:
            try:
                destination = Locality.objects.get(stoppoint=item['DestinationRef']).name
            except Locality.DoesNotExist:
                destination = html.unescape(item['DestinationName'])
            journey = VehicleJourney.objects.create(
                vehicle=vehicle,
                service=self.get_service(operator_options or operator, item),
                route_name=line_name,
                source=self.source,
                datetime=departure_time,
                destination=destination,
                code=journey_code
            )
            if journey.service and not journey.service.tracking:
                journey.service.tracking = True
                journey.service.save(update_fields=['tracking'])
            location.journey = journey

        location.datetime = ciso8601.parse_datetime(item['RecordedAtTime'])
        location.latlong = Point(float(item['Longitude']), float(item['Latitude']))
        location.heading = item['Bearing']
        location.current = True
        location.delay = round(dateparse.parse_duration(item['Delay']).total_seconds()/60)
        location.early = -location.delay

        if vehicle.latest_location:
            location.id = vehicle.latest_location.id

        location.save()
        location.redis_append()

        if not vehicle.latest_location:
            vehicle.latest_location = location
            vehicle.save(update_fields=['latest_location'])

        vehicle.update_last_modified()

    def handle_data(self, data):
        for item in data['request_data']:
            self.handle_siri_vm_vehicle(item)

        now = timezone.now()
        self.source.datetime = now
        self.source.save(update_fields=['datetime'])

        five_minutes_ago = now - timedelta(minutes=5)
        locations = VehicleLocation.objects.filter(journey__source=self.source, latest_vehicle__isnull=False)
        locations.filter(current=True, datetime__lte=five_minutes_ago).update(current=False)

    async def get_client_data(self):
        browser = await pyppeteer.launch(handleSIGINT=False)
        page = await browser.newPage()
        await page.goto(self.source.url)
        client_data = await page.evaluate('CLIENT_DATA')
        url = await page.evaluate('RTMONITOR_URI')
        origin = await page.evaluate('window.location.origin')
        await browser.close()
        return client_data, url.replace('https://', 'wss://') + 'websocket', origin

    async def sock_it(self):
        client_data, url, origin = await self.get_client_data()

        async with websockets.connect(url, origin=origin) as websocket:
            message = json.dumps({
                'msg_type': 'rt_connect',
                'client_data': client_data
            })
            await websocket.send(message)

            response = await websocket.recv()

            assert response.decode() == '{ "msg_type": "rt_connect_ok" }'

            await websocket.send('{ "msg_type": "rt_subscribe", "request_id": "A" }')

            while True:
                response = await websocket.recv()
                try:
                    await sync_to_async(self.handle_data)(json.loads(response))
                except (Error, ValueError) as e:
                    print(e)

    def handle(self, *args, **options):
        self.source = DataSource.objects.get(name='cambridge')

        while True:
            try:
                asyncio.get_event_loop().run_until_complete(self.sock_it())
            except (
                websockets.exceptions.ConnectionClosed,
                asyncio.InvalidStateError,
                pyppeteer.errors.TimeoutError
            ) as e:
                print(e)
