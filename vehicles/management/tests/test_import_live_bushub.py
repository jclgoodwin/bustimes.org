from django.test import TestCase
from busstops.models import Region, Operator, DataSource, Service
from ...models import VehicleLocation, Vehicle
from ..commands import import_bushub


class BusHubTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='WM')
        Operator.objects.create(id='DIAM', name='Graphite Buses', region_id='WM', parent='Rotala')
        Operator.objects.create(id='WNGS', name='Paul McCartney & Wings', region_id='WM', parent='Rotala')
        service_a = Service.objects.create(service_code='44a', line_name='44', date='2018-08-06', tracking=True)
        service_b = Service.objects.create(service_code='44b', line_name='44', date='2018-08-06', tracking=True)
        service_a.operator.add('DIAM')
        service_b.operator.add('DIAM')
        cls.service_c = Service.objects.create(service_code='44', line_name='44', date='2018-08-06', tracking=True)
        cls.service_c.operator.add('WNGS')
        cls.vehicle = Vehicle.objects.create(code='20052', operator_id='WNGS')
        now = '2018-08-06T22:41:15+01:00'
        cls.source = DataSource.objects.create(datetime=now)

    def test_handle(self):
        command = import_bushub.Command()
        command.source = self.source

        item = {
            "RouteDescription": None,
            "DestinationStopName": "Bus Station",
            "DestinationStopLocality": "Redditch",
            "DestinationStopFullName": "Bus Station, Redditch",
            "LastUpdated": "0001-01-01T00:00:00",
            "DepartureTime": "31/08/2018 22:45:00",
            "Latitude": "52.30236",
            "Longitude": "-1.926653",
            "RecordedAtTime": "2018-08-31T22:49:33+01:00",
            "ValidUntilTime": "2018-08-31T22:49:33+01:00",
            "LineRef": "R57",
            "DirectionRef": "outbound",
            "PublishedLineName": "44a",
            "OperatorRef": "DIAM",
            "Bearing": "143",
            "BlockRef": "2027",
            "TicketMachineServiceCode": "R57",
            "JourneyCode": "2245",
            "DbCreated": "2018-08-31T22:49:35.993",
            "DataSetId": 2091413,
            "DestinationRef": "2000G700311",
            "NextStopName": None,
            "NextStopLocality": None,
            "NextStopFullName": "",
            "StopPointRef": None,
            "CurrentStopName": "",
            "CurrentStopLocality": "",
            "CurrentStopFullName": "",
            "VehicleAtStop": False,
            "VisitNumber": "",
            "Distance": None,
            "VehicleRef": "11111",
            "Destination": None
        }

        with self.assertNumQueries(11):
            command.handle_item(item, self.source.datetime)

        with self.assertNumQueries(1):
            command.handle_item(item, self.source.datetime)

        location = VehicleLocation.objects.get()
        self.assertEqual('2018-08-31 21:49:33+00:00', str(location.datetime))
        self.assertEqual(143, location.heading)
        self.assertEqual('DIAM', location.journey.vehicle.operator_id)
        self.assertIsNone(location.journey.service)

        item['OperatorRef'] = 'WNGS'
        item['VehicleRef'] = '20052'
        item['Bearing'] = '-1'
        with self.assertNumQueries(5):
            command.handle_item(item, self.source.datetime)
        self.assertEqual(2, Vehicle.objects.count())
        self.vehicle.refresh_from_db()
        self.assertIsNotNone(self.vehicle.latest_location)
        self.assertIsNone(self.vehicle.latest_location.heading)
        self.assertEqual(self.service_c, self.vehicle.latest_location.journey.service)

        item["RecordedAtTime"] = "31/08/2018 23:10:33"
        with self.assertNumQueries(2):
            command.handle_item(item, self.source.datetime)
