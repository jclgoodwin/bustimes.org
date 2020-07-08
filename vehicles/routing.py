from django.urls import re_path
from vehicles import consumers


websocket_urlpatterns = [
    re_path(r'ws/vehicle_positions$', consumers.VehicleMapConsumer),
]
