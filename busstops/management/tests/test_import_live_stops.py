import vcr
from django.test import TestCase
from ...models import StopPoint, LiveSource
from ..commands import import_live_stops


class ImportLiveStopsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiff_stop = StopPoint.objects.create(
            pk='5710WDB48471',
            common_name='Wood Street',
            locality_centre=False,
            active=True,
            admin_area_id=1,
            locality_id=1
        )
        cls.command = import_live_stops.Command()
        cls.cardiff = LiveSource.objects.create(name='card')

    def test_import_acisconnect(self):
        self.assertEquals(0, len(self.cardiff_stop.live_sources.all()))
        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            self.command.maybe_add_acisconnect_source(self.cardiff_stop, self.cardiff, 'cardiff')
        self.assertEquals(StopPoint.objects.get(pk=self.cardiff_stop.pk).live_sources.all()[0], self.cardiff)
