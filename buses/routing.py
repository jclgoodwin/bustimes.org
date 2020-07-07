from channels.routing import ProtocolTypeRouter, URLRouter
import vehicles.routing


application = ProtocolTypeRouter({
    'websocket': URLRouter(
        vehicles.routing.websocket_urlpatterns
    )
})
