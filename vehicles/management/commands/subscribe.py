import requests
from django.core.cache import cache
from datetime import timedelta
from requests_toolbelt.adapters.source import SourceAddressAdapter
from django.utils import timezone
from django.core.management.base import BaseCommand
from busstops.models import DataSource


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--terminate',
            action='store_true'
        )

    def post(self, xml):
        print(xml)

        headers = {
           'Content-Type': 'application/xml'
        }
        response = self.session.post(self.source.url, data=xml, headers=headers, timeout=15)
        print(response, response.headers, response.text)

    def handle(self, *args, **options):
        self.source = DataSource.objects.get(name='Arriva')

        if not options['terminate']:
            if cache.get('ArrivaHeartbeat') and cache.get('ArrivaData'):
                return  # received a heartbeat recently, no need to resubscribe

        now = timezone.localtime()

        self.session = requests.Session()

        timestamp = now.isoformat()
        requestor_ref = 'HAConToBusTimesET'

        self.session.mount('http://', SourceAddressAdapter('10.16.0.6'))

        # response = self.session.get('http://icanhazip.com/')
        # print(response.text)

        # terminate any previous subscription just in case
        self.post(f"""<?xml version="1.0" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
  <TerminateSubscriptionRequest>
    <RequestTimestamp>{timestamp}</RequestTimestamp>
    <RequestorRef>{requestor_ref}</RequestorRef>
    <All></All>
  </TerminateSubscriptionRequest>
</Siri>""")

        termination_time = (now + timedelta(hours=24)).isoformat()

        # (re)subscribe
        if not options['terminate']:
            self.post(f"""<?xml version="1.0" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
  <SubscriptionRequest>
    <RequestTimestamp>{timestamp}</RequestTimestamp>
    <RequestorRef>{requestor_ref}</RequestorRef>
    <ConsumerAddress>http://68.183.252.225/siri</ConsumerAddress>
    <SubscriptionContext>
      <HeartbeatInterval>PT2M</HeartbeatInterval>
    </SubscriptionContext>
    <EstimatedTimetableSubscriptionRequest>
      <SubscriberRef>{requestor_ref}</SubscriberRef>
      <SubscriptionIdentifier>{requestor_ref}</SubscriptionIdentifier>
      <InitialTerminationTime>{termination_time}</InitialTerminationTime>
      <EstimatedTimetableRequest version="1.3">
        <RequestTimestamp>{timestamp}</RequestTimestamp>
        <PreviewInterval>PT2H</PreviewInterval>
      </EstimatedTimetableRequest>
      <ChangeBeforeUpdates>PT1M</ChangeBeforeUpdates>
    </EstimatedTimetableSubscriptionRequest>
  </SubscriptionRequest>
</Siri>""")
