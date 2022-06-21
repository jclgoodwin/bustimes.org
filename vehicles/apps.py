from django.apps import AppConfig


class VehiclesConfig(AppConfig):
    name = "vehicles"
    verbose_name = "Vehicles"

    def ready(self):
        from . import signals  # noqa
