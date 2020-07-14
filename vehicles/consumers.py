from datetime import timedelta
from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.gis.geos import Polygon, Point
from django.utils import timezone
from .models import VehicleLocation


def get_vehicle_locations(bounds):
    now = timezone.now()
    fifteen_minutes_ago = now - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(latest_vehicle__isnull=False, datetime__gte=fifteen_minutes_ago)
    locations = locations.filter(latlong__within=bounds).select_related('journey__vehicle__livery')
    return locations


class VehicleMapConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.bounds = None
        async_to_sync(self.channel_layer.group_add)('vehicle_positions', self.channel_name)
        self.accept()

    def move_vehicle(self, message):
        if self.bounds.covers(Point(*message['latlong'])):
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

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)('vehicle_positions', self.channel_name)

    def receive_json(self, content):
        new_bounds = Polygon.from_bbox(content)
        bounds = new_bounds
        if self.bounds:
            bounds -= self.bounds  # difference between new and old bounds
        self.bounds = new_bounds
        if bounds:  # if new bounds not completely covered by old bounds
            locations = get_vehicle_locations(bounds)
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
