from mock import patch
from django.test import TestCase
from busstops.models import DataSource, Region, Operator
# from .models import VehicleLocation, Call
from .tasks import handle_siri_vm


class SiriSubscriptionReceiveTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA', name='East Anglia')
        DataSource.objects.create(name='TransMach')
        Operator.objects.create(region_id='EA', id='GOCH', name='Go-Coach')

    def test_siri_vm(self):
        xml = """<Siri xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://www.kizoom.com/standards/siri/schema/1.3/siri.xsd" version="1.3">
            <ServiceDelivery>
                <ResponseTimestamp>2020-01-07T15:30:28+00:00</ResponseTimestamp>
                <ProducerRef>TRANSMACH</ProducerRef>
                <Status>true</Status>
                <MoreData>false</MoreData>
                <VehicleMonitoringDelivery version="1.3">
                    <ResponseTimestamp>2020-01-07T15:30:28+00:00</ResponseTimestamp>
                    <SubscriberRef>BusTimes</SubscriberRef>
                    <SubscriptionRef>309126</SubscriptionRef>
                    <Status>true</Status>
                    <VehicleActivity>
                        <RecordedAtTime>2020-01-07T15:30:28+00:00</RecordedAtTime>
                        <ValidUntilTime>2020-01-07T15:30:28+00:00</ValidUntilTime>
                        <MonitoredVehicleJourney>
                            <LineRef>S13</LineRef>
                            <DirectionRef>outbound</DirectionRef>
                            <FramedVehicleJourneyRef>
                                <DataFrameRef>2020-01-07</DataFrameRef>
                                <DatedVehicleJourneyRef>S13_20200107_03_30</DatedVehicleJourneyRef>
                            </FramedVehicleJourneyRef>
                            <PublishedLineName>S13</PublishedLineName>
                            <OperatorRef>GOCH</OperatorRef>
                            <VehicleLocation>
                                <Longitude>0.1839550000000000</Longitude>
                                <Latitude>51.2864000000000000</Latitude>
                            </VehicleLocation>
                            <Bearing>255</Bearing>
                            <BlockRef>0</BlockRef>
                            <VehicleRef>GOCH-8301</VehicleRef>
                        </MonitoredVehicleJourney>
                        <Extensions>
                            <VehicleJourney>
                                <Operational>
                                    <TicketMachine>
                                        <TicketMachineServiceCode>S13</TicketMachineServiceCode>
                                        <JourneyCode>2</JourneyCode>
                                    </TicketMachine>
                                </Operational>
                            </VehicleJourney>
                        </Extensions>
                    </VehicleActivity>
                    <VehicleActivity>
                        <RecordedAtTime>2020-01-07T15:30:29+00:00</RecordedAtTime>
                        <ValidUntilTime>2020-01-07T15:30:29+00:00</ValidUntilTime>
                        <MonitoredVehicleJourney>
                            <LineRef>TW10</LineRef>
                            <DirectionRef>inbound</DirectionRef>
                            <FramedVehicleJourneyRef>
                                <DataFrameRef>2020-01-07</DataFrameRef>
                                <DatedVehicleJourneyRef>TW10_20200107_03_30</DatedVehicleJourneyRef>
                            </FramedVehicleJourneyRef>
                            <PublishedLineName>TW10</PublishedLineName>
                            <OperatorRef>GOCH</OperatorRef>
                            <VehicleLocation>
                                <Longitude>0.2522650000000000</Longitude>
                                <Latitude>51.1422000000000000</Latitude>
                            </VehicleLocation>
                            <Bearing>255</Bearing>
                            <BlockRef>0</BlockRef>
                            <VehicleRef>GOCH-6001</VehicleRef>
                        </MonitoredVehicleJourney>
                        <Extensions>
                            <VehicleJourney>
                                <Operational>
                                    <TicketMachine>
                                        <TicketMachineServiceCode>TW10</TicketMachineServiceCode>
                                        <JourneyCode>2</JourneyCode>
                                    </TicketMachine>
                                </Operational>
                            </VehicleJourney>
                        </Extensions>
                    </VehicleActivity>
                </VehicleMonitoringDelivery>
            </ServiceDelivery>
        </Siri>
        """

        with self.assertNumQueries(21):
            with patch('builtins.print') as mocked_print:
                handle_siri_vm(xml)
        mocked_print.assert_called()
