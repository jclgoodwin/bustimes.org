import vcr
from freezegun import freeze_time
from django.test import TestCase, override_settings
from busstops.models import Region, Service, StopPoint, DataSource, Operator
from bustimes.models import Route, Calendar, Trip


class RifkindTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='Rifkind')

        destination = StopPoint.objects.create(common_name="Inspector Resnick's house", active=True)
        region = Region.objects.create(id='EM', name='EM')
        operator = Operator.objects.create(id='TBTN', region=region, name='Trent Burton')
        service = Service.objects.create(service_code='skylink', date='2019-06-08')
        service.operator.add(operator)
        route = Route.objects.create(service=service, source=source)
        calendar = Calendar.objects.create(start_date='2019-06-08', mon=True, tue=True, wed=True, thu=True, fri=True,
                                           sat=True, sun=True)
        Trip.objects.create(route=route, start='20:40', end='20:50', calendar=calendar, destination=destination)

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_vehicles_json(self):
        with vcr.use_cassette('data/vcr/rifkind.yaml'):

            with freeze_time('2019-06-08'):
                with self.assertNumQueries(5):
                    self.client.get('/vehicles.json?service=skylink')

            with freeze_time('2019-06-08 20:37+01:00'):
                with self.assertNumQueries(5):
                    self.client.get('/vehicles.json?service=skylink')
                with self.assertNumQueries(5):
                    res = self.client.get('/vehicles.json?service=skylink')

        json = res.json()

        self.assertEqual(len(json['features']), 0)
