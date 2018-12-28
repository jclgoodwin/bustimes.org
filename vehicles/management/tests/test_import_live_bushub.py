from django.test import TestCase
from busstops.models import Region, Operator, DataSource
from ...models import VehicleLocation
from ..commands import import_bushub


class BusHubTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='WM')
        Operator.objects.create(id='DIAM', region_id='WM')
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
            "RecordedAtTime": "31/08/2018 22:49:33",
            "ValidUntilTime": "31/08/2018 22:49:33",
            "LineRef": "R57",
            "DirectionRef": "outbound",
            "PublishedLineName": "57",
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
            "VehicleRef": "20052",
            "Destination": None
        }

        command.handle_item(item, self.source.datetime)

        location = VehicleLocation.objects.get()
        self.assertEqual('2018-08-31 21:49:33+00:00', str(location.datetime))
        self.assertEqual(143, location.heading)
        self.assertEqual('DIAM', location.journey.vehicle.operator_id)
