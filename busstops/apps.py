import os
import beeline
from django.apps import AppConfig


class BusTimesConfig(AppConfig):
    name = 'busstops'
    verbose_name = 'Bus Times'

    def ready(self):
        from . import signals  # noqa

        if os.environ.get('HONEYCOMB_KEY'):
            beeline.init(
                writekey=os.environ['HONEYCOMB_KEY'],
                dataset='bustimes',
                service_name='bustimes',
                sample_rate=40
            )
