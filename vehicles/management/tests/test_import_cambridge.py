import requests
from django.test import TestCase
from busstops.models import DataSource, Region, Operator
from ...models import Vehicle
from ..commands import import_cambridge


def error():
    raise Exception()


def timeout(*args, **kwargs):
    raise requests.exceptions.Timeout()


class CambridgeImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.command = import_cambridge.Command()
        cls.command.source = DataSource.objects.create(datetime='2019-01-20T16:16:53+00:00')
        Region.objects.create(id='EA', name='East Anglia')
        Operator.objects.create(id='SCCM', region_id='EA', name='Stagecoach Cumbernauld')
        # service = Service.objects.create(date='2010-10-10', service_code='18')
        # other_service = Service.objects.create(date='2010-10-10', service_code='36')

        # ServiceCode.objects.create(scheme='NCC Hogia', service=service, code='231')
        # ServiceCode.objects.create(scheme='NCC Hogia', service=other_service, code='240')
        # ServiceCode.objects.create(scheme='Idris Elba', service=other_service, code='231')

    def test_handle_data(self):

        data = {
            'request_data': [
                {
                    'RecordedAtTime': '2019-01-20T16:16:53+00:00',
                    'acp_ts': 1548001013,
                    'ValidUntilTime': '2019-01-20T16:16:53+00:00',
                    'VehicleMonitoringRef': 'SCCM-37220',
                    'acp_id': 'SCCM-37220',
                    'LineRef': '3',
                    'DirectionRef': 'INBOUND',
                    'DataFrameRef': '1',
                    'DatedVehicleJourneyRef': '430',
                    'PublishedLineName': '3',
                    'OperatorRef': 'SCCM',
                    'VehicleFeatureRef': 'lowFloor',
                    'OriginRef': '0590PSP592',
                    'OriginName': 'Ellwood Avenue',
                    'DestinationRef': '0590PNB058',
                    'DestinationName': 'Heltwate',
                    'OriginAimedDepartureTime': '2019-01-20T15:47:00+00:00',
                    'Monitored': 'true',
                    'InPanic': '0',
                    'Longitude': '-0.2472720',
                    'acp_lng': -0.247272,
                    'Latitude': '52.5760956',
                    'acp_lat': 52.5760956,
                    'Bearing': '348',
                    'Delay': 'PT1M34S',
                    'VehicleRef': 'SCCM-37220'
                }
            ]
        }

        self.command.handle_data(data)

        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.code, 'SCCM-37220')
        self.assertEqual(vehicle.operator.name, 'Stagecoach Cumbernauld')

        self.assertEqual(vehicle.latest_location.early, -94)
        self.assertEqual(vehicle.latest_location.journey.destination, 'Heltwate')
