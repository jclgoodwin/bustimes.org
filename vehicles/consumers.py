from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.contrib.gis.geos import Polygon
from .models import VehicleLocation


def get_vehicle_locations(bounds):
    locations = VehicleLocation.objects.filter(current=True, latest_vehicle__isnull=False)
    locations = locations.filter(latlong__within=bounds)
    return locations


class VehicleMapConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.bounds = None
        async_to_sync(self.channel_layer.group_add)('vehicle_positions', self.channel_name)
        self.accept()

    def move_vehicle(self, message):
        self.send_json([{
            'i': message['id'],
            'd': message['datetime'],
            'l': message['latlong'],
            'h': message['heading'],
            'r': message['route'],
            'c': message['css']
        }])

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)('vehicle_positions', self.channel_name)

    def receive_json(self, content):
        bounds = Polygon.from_bbox(content)

        # if not within previous bounds
        if not (self.bounds and self.bounds.covers(bounds)):
            locations = get_vehicle_locations(bounds)
            for chunk in (locations[i:i+50] for i in range(0, len(locations), 50)):
                print
                self.send_json(
                    [{
                        'i': location.id,
                        'd': str(location.datetime),
                        'l': tuple(location.latlong),
                        'h': location.heading,
                        'r': location.journey.route_name,
                        'c': location.journey.vehicle.get_livery(location.heading)
                    } for location in chunk]
                )

        self.bounds = bounds
