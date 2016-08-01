import vcr
from django.test import TestCase
from ...models import StopPoint, LiveSource
from ..commands import import_live_stops, import_tfl_stops


class ImportLiveStopsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiff_stop = StopPoint.objects.create(
            pk='5710WDB48471',
            common_name='Wood Street',
            locality_centre=False,
            active=True
        )
        cls.command = import_live_stops.Command()
        cls.cardiff = LiveSource.objects.create(name='card')
        cls.london_stop = StopPoint.objects.create(
            pk='490014721F',
            common_name='Wrong Road',
            locality_centre=False,
            active=True
        )

    def test_import_acisconnect(self):
        self.assertEquals(0, len(self.cardiff_stop.live_sources.all()))
        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            self.command.maybe_add_acisconnect_source(self.cardiff_stop, self.cardiff, 'cardiff')
        self.assertEquals(StopPoint.objects.get(pk=self.cardiff_stop.pk).live_sources.all()[0], self.cardiff)

    def test_tfl(self):
        tfl_command = import_tfl_stops.Command()

        self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': 'NONE'}))
        self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': '87'}))
        self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': '7'}))

        with vcr.use_cassette('data/vcr/tfl.yaml'):
            tfl_command.handle_row({
                'Naptan_Atco': '490014721F',
                'Heading': 42
            })

        london_stop = StopPoint.objects.get(atco_code='490014721F')
        self.assertEqual(42, london_stop.get_heading())
        self.assertEqual('Wilmot Street', london_stop.common_name)
