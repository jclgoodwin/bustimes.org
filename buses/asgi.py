import os
import django
from channels.routing import get_default_application
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "buses.settings")
django.setup()
application = get_default_application()

application = SentryAsgiMiddleware(application)
