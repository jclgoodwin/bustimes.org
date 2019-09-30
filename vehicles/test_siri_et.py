from django.test import TestCase
from django.contrib.gis.geos import Point
from busstops.models import DataSource, Region, Operator, StopPoint
from .models import VehicleLocation, Call
from .siri_et import siri_et


class SiriETTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA', name='East Anglia')
        DataSource.objects.create(name='Arriva')
        Operator.objects.create(region_id='EA', id='ANWE')
        StopPoint.objects.bulk_create([
            StopPoint(pk='069000023592', active=True, latlong=Point(0, 0)),
            StopPoint(pk='0690WNA02877', active=True, latlong=Point(0, 0)),
            StopPoint(pk='0690WNA02861', active=True, latlong=Point(0, 0)),
        ])

    def test_get(self):
        self.assertFalse(self.client.get('/siri').content)

    def test_heartbeat(self):
        self.assertIsNone(DataSource.objects.get(name='Arriva').datetime)

        response = self.client.post('/siri', 'HeartbeatNotification>', content_type='text/xml')
        self.assertTrue(response.content)
        self.assertTrue(DataSource.objects.get(name='Arriva').datetime)

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

        with self.assertNumQueries(30):
            siri_et(xml)

        with self.assertNumQueries(16):
            siri_et(xml)

        self.assertEqual(4, Call.objects.count())
        self.assertEqual(1, VehicleLocation.objects.count())
