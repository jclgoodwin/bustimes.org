import json
from django.contrib.gis.geos import Polygon
from channels.generic.websocket import WebsocketConsumer
# from channels.db import database_sync_to_async
from .models import VehicleLocation


class ChatConsumer(WebsocketConsumer):
    # @database_sync_to_async
    def get_vehicle_locations(self):
        return VehicleLocation.objects.filter(latlong__within=self.bounds)

    def connect(self):
        self.accept()
        print('connected')

    def disconnect(self, close_code):
        print('disconnected')
        pass

    def receive(self, text_data):
        bounds = json.loads(text_data)
        self.bounds = Polygon.from_bbox(bounds)
        print(self.bounds)
        locations = self.get_vehicle_locations()
        print(locations)
        self.send(text_data=json.dumps(
            [tuple(location.latlong) for location in locations]
        ))
