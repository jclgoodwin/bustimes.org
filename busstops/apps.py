from django.apps import AppConfig


class BusTimesConfig(AppConfig):
    name = "busstops"

    def ready(self):
        from . import signals  # noqa
