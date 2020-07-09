import os
from mock import patch
from vcr import use_cassette
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.conf import settings
from django.core.management import call_command
from busstops.models import Region, Operator, Service, DataSource
from vehicles.tasks import handle_siri_sx
from .models import Situation


class SiriSXTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='NW', name='North West')
        operator = Operator.objects.create(region=region, id='HATT', name='Hattons of Huyton')
        service = Service.objects.create(line_name='156', service_code='156', date='2020-01-01', current=True)
        service.operator.add(operator)
        DataSource.objects.create(name='Transport for the North', settings={'app_id': '', 'app_key': ''})
        DataSource.objects.create(name='Arriva')

    def test_get(self):
        self.assertFalse(self.client.get('/siri').content)

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_subscribe_and_hearbeat(self):
        self.assertIsNone(cache.get('Heartbeat:HAConTest'))
        self.assertIsNone(cache.get('Heartbeat:TransportAPI'))

        cassette = os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml')

        with use_cassette(cassette, match_on=['body']):
            with self.assertRaises(ValueError):
                call_command('subscribe', 'tfn')
            with self.assertRaises(ValueError):
                call_command('subscribe', 'arriva')

        response = self.client.post('/siri', """<?xml version="1.0" ?>
<Siri xmlns:ns1="http://www.siri.org.uk/siri" xmlns="http://www.siri.org.uk/siri" version="1.3">
  <HeartbeatNotification>
    <RequestTimestamp>2020-06-21T12:25:05+01:00</RequestTimestamp>
    <ProducerRef>HAConTest</ProducerRef>
    <MessageIdentifier>HAConToBusTimesET</MessageIdentifier>
    <ValidUntil>2020-06-22T02:25:02+01:00</ValidUntil>
    <ShortestPossibleCycle>PT10S</ShortestPossibleCycle>
    <ServiceStartedTime>2020-06-21T02:17:36+01:00</ServiceStartedTime>
  </HeartbeatNotification>
</Siri>""", content_type='text/xml')
        self.assertTrue(response.content)
        self.assertTrue(cache.get('Heartbeat:HAConTest'))

        cache.set('Heartbeat:TransportAPI', True)
        with use_cassette(cassette, match_on=['body']):
            call_command('subscribe', 'tfn')
            call_command('subscribe', 'arriva')

    def test_siri_sx_post(self):
        xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Siri version="2.0" xmlns="http://www.siri.org.uk/siri" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://www.siri.org.uk/siri http://www.siri.org.uk/schema/2.0/xsd/siri.xsd">
  <ServiceDelivery srsName="">
    <ResponseTimestamp>2020-07-09T16:42:27.401Z</ResponseTimestamp>
    <ProducerRef>TransportAPI</ProducerRef>
    <ResponseMessageIdentifier>f1270873-8322-43ac-97bc-16c6c1e587a6</ResponseMessageIdentifier>
    <SituationExchangeDelivery>
      <ResponseTimestamp>2020-07-09T16:42:27.401Z</ResponseTimestamp>
      <SubscriberRef>06c0099f</SubscriberRef>
      <SubscriptionRef>4bb8a34d-8e5e-4154-81e3-8129c48940d9</SubscriptionRef>
      <Situations>
        <PtSituationElement>
          <CreationTime>2020-07-09T16:40:38Z</CreationTime>
          <ParticipantRef>ItoWorld</ParticipantRef>
          <SituationNumber>RGlzcnVwdGlvbk5vZGU6MTA5NzM=</SituationNumber>
          <Version>1</Version>
          <Source>
            <SourceType>feed</SourceType>
            <TimeOfCommunication>2020-07-09T16:41:25Z</TimeOfCommunication>
          </Source>
          <Progress>open</Progress>
          <ValidityPeriod>
            <StartTime>2020-07-12T08:30:00Z</StartTime>
            <EndTime>2020-07-12T14:30:00Z</EndTime>
          </ValidityPeriod>
          <PublicationWindow>
            <StartTime>2020-07-09T16:30:00Z</StartTime>
            <EndTime>2020-07-12T14:35:59Z</EndTime>
          </PublicationWindow>
          <MiscellaneousReason>roadworks</MiscellaneousReason>
          <Planned>true</Planned>
          <Summary overridden="true" xml:lang="EN">Parrin Lane Road Closure </Summary>
          <Description overridden="true" xml:lang="EN">Parrin Lane is closed due to road maintenance
                                                       works.</Description>
          <InfoLinks>
            <InfoLink>
              <Uri/>
            </InfoLink>
          </InfoLinks>
          <Consequences>
            <Consequence>
              <Condition>unknown</Condition>
              <Severity>normal</Severity>
              <Affects>
                <Networks>
                  <AffectedNetwork>
                    <VehicleMode>bus</VehicleMode>
                    <AffectedLine>
                      <AffectedOperator>
                        <OperatorRef>GTRI</OperatorRef>
                        <OperatorName xml:lang="EN">Diamond Bus North West</OperatorName>
                      </AffectedOperator>
                      <LineRef>68</LineRef>
                      <PublishedLineName>68</PublishedLineName>
                    </AffectedLine>
                  </AffectedNetwork>
                </Networks>
                <StopPoints>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28251</StopPointRef>
                    <StopPointName xml:lang="EN">Court House</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.38160914298</Longitude>
                      <Latitude>53.50057863149</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28261</StopPointRef>
                    <StopPointName xml:lang="EN">Court House</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.38175835767</Longitude>
                      <Latitude>53.50040737395</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28271</StopPointRef>
                    <StopPointName xml:lang="EN">The Green</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37700185413</Longitude>
                      <Latitude>53.49953262204</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28281</StopPointRef>
                    <StopPointName xml:lang="EN">Sefton Drive</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37546471898</Longitude>
                      <Latitude>53.49959139406</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28291</StopPointRef>
                    <StopPointName xml:lang="EN">Bridgewater School</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37099728321</Longitude>
                      <Latitude>53.50071992117</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28301</StopPointRef>
                    <StopPointName xml:lang="EN">Bridgewater School</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.3711485051</Longitude>
                      <Latitude>53.50077338218</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28541</StopPointRef>
                    <StopPointName xml:lang="EN">Monton Church</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.35524687077</Longitude>
                      <Latitude>53.49212090009</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28551</StopPointRef>
                    <StopPointName xml:lang="EN">Monton Church</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.35514008905</Longitude>
                      <Latitude>53.49196841368</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28781</StopPointRef>
                    <StopPointName xml:lang="EN">Worsley Court House</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.38178479052</Longitude>
                      <Latitude>53.49999382018</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28791</StopPointRef>
                    <StopPointName xml:lang="EN">Worsley Court House</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.38093205679</Longitude>
                      <Latitude>53.49904376529</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28801</StopPointRef>
                    <StopPointName xml:lang="EN">Granary Lane</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37869166146</Longitude>
                      <Latitude>53.49799923824</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28811</StopPointRef>
                    <StopPointName xml:lang="EN">Granary Lane</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37819117545</Longitude>
                      <Latitude>53.49765926212</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28821</StopPointRef>
                    <StopPointName xml:lang="EN">Walker Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37580647332</Longitude>
                      <Latitude>53.49391859717</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28831</StopPointRef>
                    <StopPointName xml:lang="EN">Walker Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37512550584</Longitude>
                      <Latitude>53.49361512966</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28841</StopPointRef>
                    <StopPointName xml:lang="EN">Hartington Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37351280091</Longitude>
                      <Latitude>53.4919123738</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28851</StopPointRef>
                    <StopPointName xml:lang="EN">Westwood Crescent</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.372482314</Longitude>
                      <Latitude>53.49127741013</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28861</StopPointRef>
                    <StopPointName xml:lang="EN">Parrin Lane</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37066500379</Longitude>
                      <Latitude>53.49028534287</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28931</StopPointRef>
                    <StopPointName xml:lang="EN">Worsley Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36861412907</Longitude>
                      <Latitude>53.49015686255</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28941</StopPointRef>
                    <StopPointName xml:lang="EN">Worsley Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36724411559</Longitude>
                      <Latitude>53.4903318637</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28951</StopPointRef>
                    <StopPointName xml:lang="EN">Trevor Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36653521789</Longitude>
                      <Latitude>53.49027112188</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28961</StopPointRef>
                    <StopPointName xml:lang="EN">Trevor Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36452066861</Longitude>
                      <Latitude>53.49086153766</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28971</StopPointRef>
                    <StopPointName xml:lang="EN">May Street</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.3614359665</Longitude>
                      <Latitude>53.49145516242</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28981</StopPointRef>
                    <StopPointName xml:lang="EN">May Street</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.3609853405</Longitude>
                      <Latitude>53.49163629457</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                </StopPoints>
              </Affects>
              <Advice>
                <Details xml:lang="EN">The 68 bus route towards Farnworth will operate normal route to Monton Road,
                                       right onto Monton Green, will continue ahead onto Rocky Lane and ahead to Folly
                                       Lane, left turn to Worsley Road and then right onto Greenleach Lane to resume
                                       normal route.

The 68 bus route towards Trafford Centre will operate the reverse of the above route.

Services will observe all bus stops on the diversion route. </Details>
              </Advice>
              <Blocking>
                <JourneyPlanner>true</JourneyPlanner>
              </Blocking>
            </Consequence>
            <Consequence>
              <Condition>unknown</Condition>
              <Severity>normal</Severity>
              <Affects>
                <Networks>
                  <AffectedNetwork>
                    <VehicleMode>bus</VehicleMode>
                    <AffectedLine>
                      <AffectedOperator>
                        <OperatorRef>SCMN</OperatorRef>
                        <OperatorName xml:lang="EN">Stagecoach Greater Manchester</OperatorName>
                      </AffectedOperator>
                      <LineRef>34a</LineRef>
                      <PublishedLineName>34a</PublishedLineName>
                    </AffectedLine>
                  </AffectedNetwork>
                </Networks>
                <StopPoints>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28541</StopPointRef>
                    <StopPointName xml:lang="EN">Monton Church</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.35524687077</Longitude>
                      <Latitude>53.49212090009</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28551</StopPointRef>
                    <StopPointName xml:lang="EN">Monton Church</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.35514008905</Longitude>
                      <Latitude>53.49196841368</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28781</StopPointRef>
                    <StopPointName xml:lang="EN">Worsley Court House</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.38178479052</Longitude>
                      <Latitude>53.49999382018</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28801</StopPointRef>
                    <StopPointName xml:lang="EN">Granary Lane</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37869166146</Longitude>
                      <Latitude>53.49799923824</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28811</StopPointRef>
                    <StopPointName xml:lang="EN">Granary Lane</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37819117545</Longitude>
                      <Latitude>53.49765926212</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28821</StopPointRef>
                    <StopPointName xml:lang="EN">Walker Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37580647332</Longitude>
                      <Latitude>53.49391859717</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28831</StopPointRef>
                    <StopPointName xml:lang="EN">Walker Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37512550584</Longitude>
                      <Latitude>53.49361512966</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28841</StopPointRef>
                    <StopPointName xml:lang="EN">Hartington Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37351280091</Longitude>
                      <Latitude>53.4919123738</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28851</StopPointRef>
                    <StopPointName xml:lang="EN">Westwood Crescent</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.372482314</Longitude>
                      <Latitude>53.49127741013</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28861</StopPointRef>
                    <StopPointName xml:lang="EN">Parrin Lane</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.37066500379</Longitude>
                      <Latitude>53.49028534287</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28931</StopPointRef>
                    <StopPointName xml:lang="EN">Worsley Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36861412907</Longitude>
                      <Latitude>53.49015686255</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28941</StopPointRef>
                    <StopPointName xml:lang="EN">Worsley Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36724411559</Longitude>
                      <Latitude>53.4903318637</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28951</StopPointRef>
                    <StopPointName xml:lang="EN">Trevor Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36653521789</Longitude>
                      <Latitude>53.49027112188</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28961</StopPointRef>
                    <StopPointName xml:lang="EN">Trevor Road</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.36452066861</Longitude>
                      <Latitude>53.49086153766</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28971</StopPointRef>
                    <StopPointName xml:lang="EN">May Street</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.3614359665</Longitude>
                      <Latitude>53.49145516242</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                  <AffectedStopPoint>
                    <StopPointRef>1800NF28981</StopPointRef>
                    <StopPointName xml:lang="EN">May Street</StopPointName>
                    <Location srsName="wgs84">
                      <Longitude>-2.3609853405</Longitude>
                      <Latitude>53.49163629457</Latitude>
                    </Location>
                    <AffectedModes>
                      <Mode>
                        <VehicleMode>bus</VehicleMode>
                      </Mode>
                    </AffectedModes>
                  </AffectedStopPoint>
                </StopPoints>
              </Affects>
              <Advice>
                <Details xml:lang="EN">The 34 and 34A bus route towards Leigh/Worsley will operate normal route to
                Monton Road then right onto Monton Green continue ahead onto Rocky Lane, ahead again to Folly Lane then
                left turn onto Worsley Road to resume normal route.

Both services towards Manchester will operate normal route to Worsley Brow then will take 1st exit at the roundabout
towards Worsley Road, right turn onto Folly Lane, will continue ahead to Rocky Lane, ahead again onto Monton Green then
left onto Monton Road to resume normal route.

Services will observe all bus stops on the diverted route. </Details>
              </Advice>
              <Blocking>
                <JourneyPlanner>true</JourneyPlanner>
              </Blocking>
            </Consequence>
          </Consequences>
        </PtSituationElement>
      </Situations>
    </SituationExchangeDelivery>
  </ServiceDelivery>
</Siri>"""
        with patch('vehicles.tasks.handle_siri_sx.delay') as siri_sx:
            with self.assertNumQueries(0):
                self.client.post('/siri', xml, content_type='text/xml')
            siri_sx.assert_called_with(xml)

        with self.assertNumQueries(8):
            handle_siri_sx(xml)
        with self.assertNumQueries(2):
            handle_siri_sx(xml)

    def test_siri_sx_request(self):
        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml'), match_on=['body']):
            with self.assertNumQueries(75):
                call_command('import_siri_sx', 'hen hom', 'roger poultry')
        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml'), match_on=['body']):
            with self.assertNumQueries(11):
                call_command('import_siri_sx', 'hen hom', 'roger poultry')

        situation = Situation.objects.first()

        self.assertEqual(situation.situation_number, 'RGlzcnVwdGlvbk5vZGU6MTA3NjM=')
        self.assertEqual(situation.reason, 'roadworks')
        self.assertEqual(situation.summary, 'East Didsbury bus service changes Monday 11th May until Thursday 14th \
May. ')
        self.assertEqual(situation.text, 'Due to resurfacing works there will be bus service diversions and bus stop \
closures from Monday 11th May until Thursday 14th may. ')
        self.assertEqual(situation.reason, 'roadworks')

        response = self.client.get(situation.get_absolute_url())
        self.assertContains(response, '2020-05-10T23:01:00Z')

        consequence = situation.consequence_set.get()
        self.assertEqual(consequence.text, """Towards East Didsbury terminus customers should alight opposite East \
Didsbury Rail Station as this will be the last stop. From here its a short walk to the terminus. \n
Towards Manchester the 142 service will begin outside Didsbury Cricket club . """)

        with self.assertNumQueries(10):
            response = self.client.get('/services/156')

        self.assertContains(response, "<p>East Lancashire Road will be subjected to restrictions, at Liverpool Road,\
 from Monday 17 February 2020 for approximately 7 months.</p>")
        self.assertContains(response, "<p>Route 156 will travel as normal from St Helens to Haydock Lane, then u-turn \
at Moore Park Way roundabout, Haydock Lane, Millfield Lane, Tithebarn Road, then as normal route to Garswood (omitting \
East Lancashire Road and Liverpool Road).</p>""")

        self.assertContains(response, '<a href="https://www.merseytravel.gov.uk/travel-updates/east-lancashire-road-(haydock)/" \
rel="nofollow">www.merseytravel.gov.uk/travel-updates/east-lancashire-road-(haydock)</a>')
