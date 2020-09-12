from asgiref.sync import async_to_sync
from datetime import timedelta
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.core.cache import cache
from django.contrib.gis.geos import Polygon
from django.db.models import Exists, OuterRef, Value
from django.db.models.functions import Replace
from django.utils import timezone
from busstops.models import ServiceCode, SIRISource
from .siri_one_shot import siri_one_shot, schemes, Poorly
from .models import VehicleLocation, Channel


def get_vehicle_locations(**kwargs):
    now = timezone.now()
    fifteen_minutes_ago = now - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(**kwargs)
    locations = locations.filter(latest_vehicle__isnull=False, datetime__gte=fifteen_minutes_ago)
    locations = locations.select_related('journey__vehicle__livery')
    return locations.defer('journey__data', 'journey__vehicle__data')


class VehicleMapConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.channel = Channel(name=self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        if self.channel.id:
            self.channel.delete()

    def move_vehicle(self, message):
        self.send_json([{
            'i': message['id'],
            'd': message['datetime'],
            'l': message['latlong'],
            'h': message['heading'],
            'r': message['route'],
            'c': message['css'],
            't': message['text_colour'],
            'e': message['early']
        }])

    def receive_json(self, content):
        new_bounds = Polygon.from_bbox(content)
        bounds = new_bounds
        if self.channel.bounds:
            bounds -= self.channel.bounds  # difference between new and old bounds
        self.channel.bounds = new_bounds
        self.channel.save()
        if bounds:  # if new bounds not completely covered by old bounds
            locations = get_vehicle_locations(latlong__within=bounds)
            self.send_locations(locations)

    def send_locations(self, locations):
        # send data in batches of 50
        for chunk in (locations[i:i+50] for i in range(0, len(locations), 50)):
            self.send_json(
                [{
                    'i': location.id,
                    'd': DjangoJSONEncoder.default(None, location.datetime),
                    'l': tuple(location.latlong),
                    'h': location.heading,
                    'r': location.journey.route_name,
                    'c': location.journey.vehicle.get_livery(location.heading),
                    't': location.journey.vehicle.get_text_colour(),
                    'e': location.early
                } for location in chunk]
            )


class ServiceMapConsumer(VehicleMapConsumer):
    def connect(self):
        self.accept()
        self.service_ids = self.scope['url_route']['kwargs']['service_ids'].split(',')
        locations = get_vehicle_locations(journey__service__in=self.service_ids)
        self.send_locations(locations)
        if not locations:
            self.send_json([])
        icarus = not any(location.journey.source_id != 75 for location in locations)
        for service_id in self.service_ids:
            async_to_sync(self.channel_layer.group_add)(f'service{service_id}', self.channel_name)
            if icarus:
                codes = ServiceCode.objects.filter(scheme__in=schemes, service=service_id)
                codes = codes.annotate(source_name=Replace('scheme', Value(' SIRI')))
                siri_sources = SIRISource.objects.filter(name=OuterRef('source_name'))
                codes = codes.filter(Exists(siri_sources))
                for code in codes:
                    try:
                        siri_one_shot(code, timezone.now(), bool(locations))
                        break
                    except Poorly:
                        pass
        cache.close()

    def disconnect(self, close_code):
        for service_id in self.service_ids:
            async_to_sync(self.channel_layer.group_discard)(f'service{service_id}', self.channel_name)

    def recieve_json(self, content):
        pass
