import requests
import datetime
from requests_toolbelt.adapters.source import SourceAddressAdapter
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--terminate',
            action='store_true'
        )

    def handle(self, *args, **options):
        session = requests.Session()

        now = datetime.datetime.now()
        timestamp = now.isoformat()
        termination_time = (now + datetime.timedelta(minutes=5)).isoformat()
        requestor_ref = 'HAConToBusTimesET'

        session.mount('http://', SourceAddressAdapter('10.16.0.6'))

        response = session.get('http://icanhazip.com/')
        print(response.text)
        return

        if options['terminate']:
            xml = f"""
<?xml version="1.0" ?>
<ns1:Siri xmlns:ns1="http://www.siri.org.uk/siri" version="1.3">
  <ns1:TerminateSubscriptionRequest>
    <ns1:RequestTimestamp>{timestamp}</ns1:RequestTimestamp>
    <ns1:RequestorRef>{requestor_ref}</ns1:RequestorRef>
    <ns1:All></ns1:All>
  </ns1:TerminateSubscriptionRequest>
</ns1:Siri>"""
        else:
            xml = f"""
<?xml version="1.0" ?>
<ns1:Siri xmlns:ns1="http://www.siri.org.uk/siri" version="1.3">
  <ns1:SubscriptionRequest>
    <ns1:RequestTimestamp>{timestamp}</ns1:RequestTimestamp>
    <ns1:RequestorRef>{requestor_ref}</ns1:RequestorRef>
    <ns1:ConsumerAddress>http://68.183.252.225/siri</ns1:ConsumerAddress>
    <ns1:SubscriptionContext>
      <ns1:HeartbeatInterval>PT20S</ns1:HeartbeatInterval>
    </ns1:SubscriptionContext>
    <ns1:EstimatedTimetableSubscriptionRequest>
      <ns1:SubscriberRef>{requestor_ref}</ns1:SubscriberRef>
      <ns1:SubscriptionIdentifier>{requestor_ref}</ns1:SubscriptionIdentifier>
      <ns1:InitialTerminationTime>{termination_time}</ns1:InitialTerminationTime>
      <ns1:EstimatedTimetableRequest version="1.3">
        <ns1:RequestTimestamp>{timestamp}</ns1:RequestTimestamp>
        <ns1:PreviewInterval>PT2H</ns1:PreviewInterval>
      </ns1:EstimatedTimetableRequest>
      <ns1:ChangeBeforeUpdates>PT1M</ns1:ChangeBeforeUpdates>
    </ns1:EstimatedTimetableSubscriptionRequest>
  </ns1:SubscriptionRequest>
</ns1:Siri>
        """

        print(xml)
        url = 'http://gate-nat.hacon.de:26747'
        headers = {
           'Content-Type': 'application/xml'
        }
        response = session.post(url, data=xml, headers=headers, timeout=15)
        print(response, response.headers, response.text)
