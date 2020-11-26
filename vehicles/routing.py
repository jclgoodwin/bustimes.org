from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from vehicles import consumers, workers


application = ProtocolTypeRouter({
    "websocket": URLRouter((
        re_path(r'^ws/vehicle_positions$', consumers.VehicleMapConsumer.as_asgi()),
        re_path(r'^ws/vehicle_positions/services/(?P<service_ids>[\d,]+)$', consumers.ServiceMapConsumer.as_asgi()),
        re_path(r'^ws/vehicle_positions/operators/(?P<operator_id>[\w]+)$', consumers.OperatorMapConsumer.as_asgi()),
    )),
    "channel": ChannelNameRouter({
        "sirivm": workers.SiriConsumer()
    })
})
