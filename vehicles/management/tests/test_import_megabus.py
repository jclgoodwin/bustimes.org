from django.test import TestCase
from busstops.models import DataSource, Region, Operator
from ...models import Vehicle
from ..commands.import_megabus import Command


class MegabusTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(name="Megabus")
        cls.command = Command()
        cls.command.do_source()

        gb = Region.objects.create(id="GB")
        Operator.objects.create(id="MEGA", name="Megabus", region=gb)

    def test_handle_item(self):
        item = {
            'reference': '210310CL774304', 'id': '210310CL774304',
            'depart': 'Glasgow', 'arrival': 'Aberdeen', 'route': 'M9', 'date': '2021-03-10', 'linkDate': '2021-03-10',
            'startTime': {'dateTime': '2021-03-10 22:30:00', 'hrs': '22', 'mins': '30', 'time': '22:30'},
            'live': {
                'vehicle': '54123', 'vehicleId': '54123', 'lat': 56.89718, 'lon': -2.3807,
                'geoLocation': 'A90, Scotland', 'bearing': 40, 'status': '1',
                'timestamp': {'dateTime': '2021-03-28 01:17:03', 'hrs': '01', 'mins': '17', 'time': '01:17'}
            }
        }
        self.command.handle_item(item)
        vehicle = Vehicle.objects.get()
        self.assertEqual('54123', str(vehicle))
        self.assertEqual('11 Mar 2021 01:17:03', str(vehicle.latest_location))
        self.assertEqual('28 Mar 21 22:30 M9   to Aberdeen', str(vehicle.latest_journey))
