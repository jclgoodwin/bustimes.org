from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, ChannelNameRouter
from . import workers


application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # this prevents weird problems with parallel requests with the development server

    "channel": ChannelNameRouter({
        "sirivm": workers.SiriConsumer()
    })
})
