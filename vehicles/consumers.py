from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.contrib.gis.geos import Polygon
from .models import VehicleLocation


def get_vehicle_locations(bounds):
    locations = VehicleLocation.objects.filter(current=True, latest_vehicle__isnull=False)
    locations = locations.filter(latlong__within=bounds)  # .select_related('journey__vehicle__livery')
    return locations


class VehicleMapConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.bounds = None
        async_to_sync(self.channel_layer.group_add)('vehicle_positions', self.channel_name)
        self.accept()

    def move_vehicle(self, foo):
        print(foo)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)('vehicle_positions', self.channel_name)

    def receive_json(self, content):
        bounds = Polygon.from_bbox(content)

        # if not within previous bounds
        if not (self.bounds and self.bounds.covers(bounds)):
            locations = get_vehicle_locations(bounds)
            self.send_json(
                [{
                    'i': location.id,
                    'l': tuple(location.latlong),
                    'h': location.heading
                } for location in locations]
            )

        self.bounds = bounds
