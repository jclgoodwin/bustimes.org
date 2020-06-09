from django.test import TestCase
from busstops.models import Service, SIRISource, Region, Operator
from .models import Vehicle
from . import tasks


class VehiclesTasksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.siri_source = SIRISource.objects.create(name='HP')

        ea = Region.objects.create(id='EA', name='East Anglia')

        cls.badgerline = Operator.objects.create(region=ea, name='Badgerine', id='BADG', slug='badgerline',
                                                 parent='First')

        cls.service = Service.objects.create(service_code='49', date='2018-12-25', tracking=True,
                                             description='Spixworth - Hunworth - Happisburgh')
        cls.service.operator.add(cls.badgerline)

    def test_create_service_code(self):
        tasks.create_service_code('Kingfisher', self.service.id, 'Sutton SIRI')

        code = self.service.servicecode_set.get()
        self.assertEqual('Sutton SIRI', code.scheme)
        self.assertEqual('Kingfisher', code.code)

    def test_create_journey_code(self):
        tasks.create_journey_code('Brazen Bottom', self.service.id, '601', self.siri_source.id)

        code = self.service.journeycode_set.get(siri_source=self.siri_source)
        self.assertEqual('Brazen Bottom', code.destination)
        self.assertEqual('601', code.code)

    def test_log_vehicle_journey(self):
        with self.assertNumQueries(1):
            tasks.log_vehicle_journey(
                'FMR', 'FMR-66692', None, '49', '2019-02-09T12:10:00Z', '311_4560_220', 'EVESHAM Bus Station',
                'Worcestershire', 'http://worcestershire-rt-http.trapezenovus.co.uk:8080'
            )
        self.assertFalse(Vehicle.objects.exists())

        with self.assertNumQueries(12):
            tasks.log_vehicle_journey(
                'FMR', 'FMR-66692', self.service.id, '49', '2019-02-09T12:10:00Z', '311_4560_220', 'EVESHAM Bus Station',
                'Worcestershire', 'http://worcestershire-rt-http.trapezenovus.co.uk:8080'
            )

        with self.assertNumQueries(5):
            tasks.log_vehicle_journey(
                'FMR', 'FMR-66692', self.service.id, '49', '2019-02-09T12:10:00Z', '311_4560_220', 'EVESHAM Bus Station',
                'Worcestershire', 'http://worcestershire-rt-http.trapezenovus.co.uk:8080'
            )

        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.code, '66692')
        self.assertEqual(vehicle.operator, self.badgerline)
