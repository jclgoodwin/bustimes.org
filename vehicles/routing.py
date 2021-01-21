from django.urls import re_path
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from vehicles import consumers


application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # this prevents weird problems with parallel requests with the development server

    "websocket": URLRouter((
        re_path(r'^ws/vehicle_positions$', consumers.VehicleMapConsumer.as_asgi()),
        re_path(r'^ws/vehicle_positions/services/(?P<service_ids>[\d,]+)$', consumers.ServiceMapConsumer.as_asgi()),
        re_path(r'^ws/vehicle_positions/operators/(?P<operator_id>[\w]+)$', consumers.OperatorMapConsumer.as_asgi()),
    )),
})
