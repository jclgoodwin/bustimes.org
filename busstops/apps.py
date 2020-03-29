from django.apps import AppConfig
import beeline


class BusTimesConfig(AppConfig):
    name = 'busstops'
    verbose_name = 'Bus Times'

    def ready(self):
        from . import signals  # noqa

        beeline.init(
            writekey='2f5760a541bc6d06cdd8bccdbebbcfb4',
            dataset='bustimes',
            service_name='bustimes'
        )

