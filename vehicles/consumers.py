import json
from django.contrib.gis.geos import Polygon
from channels.generic.websocket import WebsocketConsumer
# from channels.db import database_sync_to_async
from .models import VehicleLocation


def get_vehicle_locations(bounds):
    return VehicleLocation.objects.filter(latlong__within=bounds, current=True, latest_vehicle__isnull=False)


class ChatConsumer(WebsocketConsumer):
    # @database_sync_to_async

    def connect(self):
        self.bounds = None
        self.accept()
        print('connected')

    def disconnect(self, close_code):
        print('disconnected')
        pass

    def receive(self, text_data):
        bounds = json.loads(text_data)  # (xmin, ymin, xmax, ymax)
        bounds = Polygon.from_bbox(bounds)

        # if not within previous bounds
        if not (self.bounds and self.bounds.covers(bounds)):
            locations = get_vehicle_locations(bounds)
            self.send(text_data=json.dumps(
                [{
                    'i': location.id,
                    'l': tuple(location.latlong)
                } for location in locations]
            ))

        self.bounds = bounds
