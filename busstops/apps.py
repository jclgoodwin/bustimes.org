from django.apps import AppConfig


class BusTimesConfig(AppConfig):
    name = 'busstops'
    verbose_name = 'Bus Times'

    def ready(self):
        from . import signals  # noqa
