from django.test import TestCase
from django.contrib.gis.geos import Point
from busstops.models import DataSource, Region, Operator, StopPoint
from .models import VehicleLocation, Call
from .tasks import handle_siri_vm, handle_siri_et


class SiriETTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA', name='East Anglia')
        DataSource.objects.create(name='Arriva')
        DataSource.objects.create(name='TransMach')
        Operator.objects.create(region_id='EA', id='ANWE', name='Arrivederci')
        Operator.objects.create(region_id='EA', id='GOCH', name='Go-Coach')
        StopPoint.objects.bulk_create([
            StopPoint(pk='069000023592', active=True, latlong=Point(0, 0)),
            StopPoint(pk='0690WNA02877', active=True, latlong=Point(0, 0)),
            StopPoint(pk='0690WNA02861', active=True, latlong=Point(0, 0)),
        ])

    def test_siri_et(self):
        xml = """<?xml version="1.0" encoding="utf-8" ?>
<Siri xmlns:ns1="http://www.siri.org.uk/siri" xmlns="http://www.siri.org.uk/siri"
xmlns:xml="http://www.w3.org/XML/1998/namespace" version="1.3">
 <ServiceDelivery>
   <ResponseTimestamp>2019-09-02T16:36:40+01:00</ResponseTimestamp>
   <ProducerRef>HAConTest</ProducerRef>
   <MoreData>false</MoreData>
   <EstimatedTimetableDelivery version="1.3">
     <ResponseTimestamp>2019-09-02T16:36:39+01:00</ResponseTimestamp>
     <SubscriberRef>HAConToBusTimesET</SubscriberRef>
     <SubscriptionRef>HAConToBusTimesET</SubscriptionRef>
     <Status>true</Status>
     <ValidUntil>2019-09-02T17:17:08+01:00</ValidUntil>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>37</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_F0371039</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">37</PublishedLineName>
         <DirectionName xml:lang="EN">Winsford Guildhall</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2934</VehicleRef>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>500</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_500_1086</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">500</PublishedLineName>
         <DirectionName xml:lang="EN">Murdishaw Cen.</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-5017</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>0690WNA02877</StopPointRef>
             <VisitNumber>64</VisitNumber>
             <StopPointName xml:lang="EN">Ditton Crossway</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>110</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_N1101083</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">110</PublishedLineName>
         <DirectionName xml:lang="EN">Warrington Bus Interchange</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-5006</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>069000023592</StopPointRef>
             <VisitNumber>1</VisitNumber>
             <StopPointName xml:lang="EN">Cuerdley Cross Golf Centre</StopPointName>
             <AimedDepartureTime>2019-09-02T16:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0690WNA02877</StopPointRef>
             <VisitNumber>2</VisitNumber>
             <StopPointName xml:lang="EN">Doe Green Tannery Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0690WNA02861</StopPointRef>
             <VisitNumber>3</VisitNumber>
             <StopPointName xml:lang="EN">Warrington Bus Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 7</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
   </EstimatedTimetableDelivery>
 </ServiceDelivery>
</Siri>
        """

        with self.assertNumQueries(34):
            handle_siri_et(xml)

        with self.assertNumQueries(17):
            handle_siri_et(xml)

        self.assertEqual(4, Call.objects.count())
        self.assertEqual(1, VehicleLocation.objects.count())

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
            handle_siri_vm(xml)
