from asgiref.sync import async_to_sync
from datetime import timedelta
from channels.generic.websocket import JsonWebsocketConsumer
from django.contrib.gis.geos import Polygon
from django.utils import timezone
from .models import VehicleLocation, Channel


def get_vehicle_locations(**kwargs):
    now = timezone.now()
    fifteen_minutes_ago = now - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(**kwargs)
    locations = locations.filter(vehicle__isnull=False, datetime__gte=fifteen_minutes_ago)
    locations = locations.select_related('journey', 'vehicle')
    return locations.defer('journey__data', 'vehicle__data')


class VehicleMapConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.channel = Channel(name=self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        if self.channel.id:
            self.channel.delete()

    def move_vehicles(self, message):
        self.send_json(message['items'])

    def receive_json(self, content):
        try:
            new_bounds = Polygon.from_bbox(content)
        except ValueError:
            return
        bounds = new_bounds
        if self.channel.bounds:
            bounds -= self.channel.bounds  # difference between new and old bounds
        self.channel.bounds = new_bounds
        self.channel.datetime = timezone.now()
        self.channel.save()
        if bounds:  # if new bounds not completely covered by old bounds
            locations = get_vehicle_locations(latlong__bboverlaps=bounds)
            self.send_locations(locations)

    def send_locations(self, locations):
        if locations:
            for chunk in (locations[i:i+1000] for i in range(0, len(locations), 1000)):
                self.send_json([location.get_websocket_json() for location in chunk])


class ServiceMapConsumer(VehicleMapConsumer):
    def connect(self):
        self.accept()
        service_ids = self.scope['url_route']['kwargs']['service_ids'].split(',')
        locations = get_vehicle_locations(journey__service__in=service_ids)
        if locations:
            self.send_locations(locations)
        else:
            self.send_json([])
        for service_id in service_ids:
            group = f'service{service_id}'
            self.groups.append(group)
            async_to_sync(self.channel_layer.group_add)(group, self.channel_name)

    def disconnect(self, close_code):
        pass

    def recieve_json(self, content):
        pass


class OperatorMapConsumer(ServiceMapConsumer):
    def connect(self):
        self.accept()
        operator_id = self.scope['url_route']['kwargs']['operator_id']
        locations = get_vehicle_locations(vehicle__operator=operator_id)
        self.send_locations(locations)
        group = f'operator{operator_id}'
        self.groups.append(group)
        async_to_sync(self.channel_layer.group_add)(group, self.channel_name)
