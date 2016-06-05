import vcr
import live
from django.test import TestCase
from busstops.models import StopPoint, Service


class LiveDeparturesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.london_stop = StopPoint.objects.create(
            pk='490014721F',
            common_name='Wilmot Street',
            locality_centre=False,
            active=True,
            admin_area_id=1,
            locality_id=1
        )

    def test_tfl(self):
        stop = StopPoint.objects.get(pk='490014721F')
        with vcr.use_cassette('data/vcr/tfl.yaml'):
            departures = live.TflDepartures(stop, Service.objects.all()).get_departures()
        row = departures.next()
        self.assertEqual('Stratford City', row['destination'])
        self.assertEqual('388', row['service'])
        self.assertEqual(2016, row['time'].date().year)
        self.assertEqual(6, row['time'].date().month)
        self.assertEqual(5, row['time'].date().day)
