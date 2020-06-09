from django.test import TestCase
from busstops.models import Service, SIRISource
from .models import Vehicle
from . import tasks


class VehiclesTasksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.siri_source = SIRISource.objects.create(name='HP')

        # ea = Region.objects.create(id='EA', name='East Anglia')

        # cls.wifi = VehicleFeature.objects.create(name='Wi-Fi')
        # cls.usb = VehicleFeature.objects.create(name='USB')

        # cls.bova = Operator.objects.create(region=ea, name='Bova and Over', id='BOVA', slug='bova-and-over',
        #                                    parent='Madrigal Electromotive')
        # cls.lynx = Operator.objects.create(region=ea, name='Lynx', id='LYNX', slug='lynx',
        #                                    parent='Madrigal Electromotive')

        # tempo = VehicleType.objects.create(name='Optare Tempo', coach=False, double_decker=False)
        # spectra = VehicleType.objects.create(name='Optare Spectra', coach=False, double_decker=True)

        cls.service = Service.objects.create(service_code='49', date='2018-12-25', tracking=True,
                                             description='Spixworth - Hunworth - Happisburgh')

        # service.operator.add(cls.lynx)
        # service.operator.add(cls.bova)

        # cls.vehicle_1 = Vehicle.objects.create(code='2', fleet_number=1, reg='FD54JYA', vehicle_type=tempo,
        #                                        colours='#FF0000', notes='Trent Barton', operator=cls.lynx)
        # livery = Livery.objects.create(colours='#FF0000 #0000FF')
        # cls.vehicle_2 = Vehicle.objects.create(code='50', fleet_number=50, reg='UWW2X', livery=livery,
        #                                        vehicle_type=spectra, operator=cls.lynx, data={'Depot': 'Long Sutton'})

        # journey = VehicleJourney.objects.create(vehicle=cls.vehicle_1, datetime=cls.datetime, source=source,
        #                                         service=service, route_name='2')

        # location = VehicleLocation.objects.create(datetime=cls.datetime, latlong=Point(0, 51),
        #                                           journey=journey, current=True)
        # cls.vehicle_1.latest_location = location
        # cls.vehicle_1.save()

        # cls.vehicle_1.features.set([cls.wifi])

        # cls.user = User.objects.create(username='josh', is_staff=True, is_superuser=True)

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
        tasks.log_vehicle_journey(
            'FMR', 'FMR-66692', None, 'X50', '2019-02-09T12:10:00Z', '311_4560_220', 'EVESHAM Bus Station',
            'Worcestershire', 'http://worcestershire-rt-http.trapezenovus.co.uk:8080'
        )
        vehicle = Vehicle.objects.get()
