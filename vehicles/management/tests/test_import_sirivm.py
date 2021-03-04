import os
from vcr import use_cassette
from django.test import TestCase
from busstops.models import Region, Operator, Service, OperatorCode, DataSource
from ...models import VehicleLocation
from ..commands import import_sirivm


DIR = os.path.dirname(os.path.abspath(__file__))


class SiriVMImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA')
        cls.operator = Operator.objects.create(id='FESX', region_id='EA')
        cls.service = Service.objects.create(service_code='73', line_name='73', date='2010-01-01', tracking=True)
        cls.service.operator.set(['FESX'])
        cls.command = import_sirivm.Command()
        cls.command.source = DataSource.objects.create(
            name='Essex SIRI', datetime='2018-08-06T22:41:15+01:00',
            url='http://essex.jmwrti.co.uk:8080/RTI-SIRI-Server/SIRIHandler')
        OperatorCode.objects.create(operator=cls.operator, source=cls.command.source, code='FE')
        # JourneyCode.objects.create(service=cls.service, code='14', destination='Hundred Acre Wood')

    @use_cassette(os.path.join(DIR, 'vcr', 'import_sirivm.yaml'), decode_compressed_response=True)
    def test_handle(self):
        items = self.command.get_items()
        item = next(items)

        vehicle, vehicle_created = self.command.get_vehicle(item)
        journey = self.command.get_journey(item, vehicle)

        self.assertEqual('14', journey.code)
        # self.assertEqual('Hundred Acre Wood', journey.destination)
        self.assertEqual('69532', str(vehicle))
        self.assertTrue(vehicle_created)
        self.assertEqual(self.service, journey.service)
        self.assertEqual(self.operator, vehicle.operator)

        location = self.command.create_vehicle_location(item)
        self.assertIsNone(location.heading)

        self.assertEqual('2018-08-06 21:44:32+01:00', str(self.command.get_datetime(item)))

        locations = VehicleLocation.objects.filter(journey__source=self.command.source)

        with self.assertNumQueries(6):
            self.command.handle_item(item)
            self.command.save()
        self.assertIsNone(locations.get().heading)

        # if datetime is the same, shouldn't create new vehicle location
        with self.assertNumQueries(1):
            self.command.handle_item(item)
            self.command.save()
        self.assertEqual(1, locations.count())

        # different datetime - should create new vehicle location
        item['RecordedAtTime'] = '2018-08-06T21:45:32+01:00'
        with self.assertNumQueries(1):
            self.command.handle_item(item)
            self.command.save()

        # another different datetime
        item['RecordedAtTime'] = '2018-08-06T21:46:32+01:00'
        with self.assertNumQueries(1):
            self.command.handle_item(item)
            self.command.save()

        self.assertEqual(1, locations.count())
        last_location = locations.last()
        self.assertIsNone(last_location.heading)
        # self.assertEqual(last_location.early, -8)

        # test an item with an invalid delay ('-PT2M.492S')
        with self.assertNumQueries(0):
            item = next(items)
        location = self.command.create_vehicle_location(item)
        self.assertIsNone(location.early)

    def test_devonshire(self):
        item = {
            "RecordedAtTime": "2018-12-27T16:26:42Z",
            "ItemIdentifier": "f3d015d8-8cd4-4146-9b45-42bb2a4dd0b6",
            "ValidUntilTime": "2018-12-27T16:26:42Z",
            "VehicleMonitoringRef": "DTCO-106",
            "MonitoredVehicleJourney": {
                "LineRef": "184",
                "DirectionRef": "none",
                "FramedVehicleJourneyRef": {
                    "DataFrameRef": "2018-12-27",
                    "DatedVehicleJourneyRef": "1607"
                },
                "JourneyPatternRef": "624836",
                "VehicleMode": "bus",
                "PublishedLineName": "184",
                "DirectionName": "none",
                "OperatorRef": "DTCO",
                "OriginRef": "1100DEC11150",
                "OriginName": "Railway Station",
                "Via": [{
                    "PlaceName": "Bishopsteignton"
                }, {
                    "PlaceName": "Kingsteignton"
                }, {
                    "PlaceName": "Newton Abbot"
                }],
                "DestinationRef": "1100DEM55095",
                "DestinationName": "Rail Station",
                "OriginAimedDepartureTime": "2018-12-27T16:07:00Z",
                "DestinationAimedArrivalTime": "2018-12-27T16:51:00Z",
                "Monitored": "true",
                "VehicleLocation": {
                    "Longitude": "-3.5089750591636",
                    "Latitude": "50.5476417184896"
                },
                "Bearing": "240",
                "Delay": "PT5M32S",
                "BlockRef": "UN.DTCO.31-184-A-y10-1.1607.Inb",
                "VehicleRef": "DTCO-102"
            }
        }
        self.command.handle_item(item)
        self.command.save()
        location = VehicleLocation.objects.get()
        self.assertEqual(240, location.heading)
        self.assertEqual('1607', location.journey.code)
        self.assertEqual('Rail Station', location.journey.destination)
