import asyncio
import websockets
import ciso8601
import json
import html
from pyppeteer import launch
from datetime import timedelta
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone, dateparse
from busstops.models import Operator, Service, DataSource
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
            defaults = {'fleet_number': vehicle}
        if type(operator) is Operator:
            return self.vehicles.get_or_create(defaults, operator=operator, code=vehicle)
        defaults = {'operator_id': operator[0]}
        return self.vehicles.get_or_create(defaults, operator__in=operator, code=vehicle)

    def get_service(self, operator, item):
        line_name = item['PublishedLineName']

        if type(operator) is Operator:
            service = operator.service_set
            if operator.pk == 'WHIP' and line_name == 'U':
                line_name = 'Universal U'
        else:
            service = Service.objects.filter(operator__in=operator)
            if operator[0] == 'SCCM' and line_name == 'NG1':
                line_name = 'NG01'
        service = service.filter(current=True)

        if line_name.startswith('PR'):
            service = service.filter(pk__contains='-{}-'.format(line_name))
        else:
            service = service.filter(line_name=line_name)

        try:
            try:
                return service.get()
            except Service.MultipleObjectsReturned:
                return service.filter(Q(stops=item['OriginRef']) | Q(stops=item['DestinationRef'])).distinct().get()
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
        with transaction.atomic():
            line_name = item['PublishedLineName']
            journey_code = item['DatedVehicleJourneyRef']
            if not created and vehicle.latest_location and vehicle.latest_location.current:
                latest_location = vehicle.latest_location
                latest_location.current = False
                latest_location.save()
                if line_name == latest_location.journey.route_name and journey_code == latest_location.journey.code:
                    journey = vehicle.latest_location.journey
            if not journey:
                journey = VehicleJourney.objects.create(
                    vehicle=vehicle,
                    service=self.get_service(operator_options or operator, item),
                    route_name=line_name,
                    source=self.source,
                    datetime=ciso8601.parse_datetime(item['OriginAimedDepartureTime']),
                    destination=html.unescape(item['DestinationName']),
                    code=journey_code
                )
            delay = item['Delay']
            early = -round(dateparse.parse_duration(delay).total_seconds()/60)
            vehicle.latest_location = VehicleLocation.objects.create(
                journey=journey,
                datetime=ciso8601.parse_datetime(item['RecordedAtTime']),
                latlong=Point(float(item['Longitude']), float(item['Latitude'])),
                heading=item['Bearing'],
                current=True,
                early=early
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

    async def get_client_data(self):
        browser = await launch()
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
                self.handle_data(json.loads(response))

    def handle(self, *args, **options):
        self.source = DataSource.objects.get(name='cambridge')

        while True:
            try:
                asyncio.get_event_loop().run_until_complete(self.sock_it())
            except (websockets.exceptions.ConnectionClosed, asyncio.base_futures.InvalidStateError) as e:
                print(e)
