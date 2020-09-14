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

            if item['OperatorRef'] == 'WPB':
                return None, None

        vehicles = self.vehicles
        if type(operator) is tuple:
            defaults['operator_id'] = operator[0]
            if operator[0] == 'SCCM':
                vehicles = vehicles.filter(operator__parent='Stagecoach')
            else:
                vehicles = vehicles.filter(operator__in=operator)
        elif operator:
            defaults['operator'] = operator
            vehicles = vehicles.filter(operator=operator)
        else:
            vehicles = vehicles.filter(operator=None)

        if not vehicle.isdigit() and len(vehicle) == 7:
            defaults['code'] = vehicle
            return vehicles.get_or_create(defaults, reg=vehicle)
        return vehicles.get_or_create(defaults, code=vehicle)

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
        operator_options = None
        operator = self.get_operator(item['OperatorRef'])
        if not operator:
            print(item)
        elif operator.pk == 'SCCM':
            operator_options = ('SCCM', 'SCPB', 'SCHU', 'SCBD')
        elif operator.pk == 'CBBH':
            operator_options = ('CBBH', 'CBNL')

        vehicle, created = self.get_vehicle(operator_options or operator, item)

        if not vehicle:
            return

        journey = None

        if 'PublishedLineName' in item:
            line_name = item['PublishedLineName']
            journey_code = item['DatedVehicleJourneyRef']
            if journey_code == 'UNKNOWN':
                journey_code = ''
            departure_time = ciso8601.parse_datetime(item['OriginAimedDepartureTime'])
        else:
            line_name = ''
            journey_code = ''
            departure_time = None

        recorded_at_time = ciso8601.parse_datetime(item['RecordedAtTime'])

        if not created and vehicle.latest_location:
            location = vehicle.latest_location
            latest_journey = location.journey
            if latest_journey.datetime == departure_time:
                journey = latest_journey
            elif departure_time:
                journey = vehicle.vehiclejourney_set.filter(datetime=departure_time).first()
        else:
            location = VehicleLocation()

        if not journey:
            if 'DestinationRef' in item:
                try:
                    destination = Locality.objects.get(stoppoint=item['DestinationRef']).name
                except Locality.DoesNotExist:
                    destination = html.unescape(item['DestinationName'])
            else:
                destination = ''
            if line_name:
                service = self.get_service(operator_options or operator, item)
            else:
                service = None
                destination = ''

                departure_time = recorded_at_time
            journey = VehicleJourney.objects.create(
                vehicle=vehicle,
                service=service,
                route_name=line_name,
                source=self.source,
                datetime=departure_time,
                destination=destination,
                code=journey_code
            )
            if not departure_time:
                departure_time = ciso8601.parse_datetime(item['RecordedAtTime'])
            journey_kwargs = {
                'vehicle': vehicle,
                'service': service,
                'route_name': line_name,
                'datetime': departure_time,
                'destination': destination,
                'code': journey_code
            }
            journey = VehicleJourney.objects.filter(**journey_kwargs).first()
            if not journey:
                journey = VehicleJourney.objects.create(**journey_kwargs, source=self.source)
            if journey.service and not journey.service.tracking:
                journey.service.tracking = True
                journey.service.save(update_fields=['tracking'])
            location.journey = journey

        location.datetime = recorded_at_time
        location.latlong = Point(float(item['Longitude']), float(item['Latitude']))
        location.heading = item['Bearing']
        location.current = True
        location.delay = round(dateparse.parse_duration(item['Delay']).total_seconds()/60)
        location.early = -location.delay

        if vehicle.latest_location:
            location.id = vehicle.latest_location.id

        location.save()
        location.redis_append()
        location.channel_send(vehicle)

        if not vehicle.latest_location:
            vehicle.latest_location = location
            vehicle.save(update_fields=['latest_location'])

    def handle_data(self, data):
        for item in data['request_data']:
            try:
                self.handle_siri_vm_vehicle(item)
            except KeyError as e:
                print(e, item)

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

        asyncio.get_event_loop().run_until_complete(self.sock_it())
