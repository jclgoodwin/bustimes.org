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
        headers = {
           'Content-Type': 'application/xml'
        }
        xml = f'<?xml version="1.0" ?><Siri xmlns="http://www.siri.org.uk/siri" version="1.3">{xml}'
        self.session.post(self.source.url, data=xml.replace('    ', ''), headers=headers, timeout=5)

    def terminate_subscription(self, timestamp, requestor_ref):
        self.post(f"""
            <TerminateSubscriptionRequest>
                <RequestTimestamp>{timestamp}</RequestTimestamp>
                <RequestorRef>{requestor_ref}</RequestorRef>
                <All/>
            </TerminateSubscriptionRequest>
        """)

    def subscribe(self, timestamp, requestor_ref, consumer_address, xml):
        self.post(f"""
            <SubscriptionRequest>
                <RequestTimestamp>{timestamp}</RequestTimestamp>
                <RequestorRef>{requestor_ref}</RequestorRef>
                <ConsumerAddress>{consumer_address}</ConsumerAddress>
                {xml}
            </SubscriptionRequest>
        """)

    def tfn(self, app_id, terminate):
        self.source = DataSource.objects.get(name='Transport for the North')

        if not terminate and cache.get('Heartbeat:TransportAPI'):
            return  # received a heartbeat recently, no need to resubscribe

        now = timezone.localtime()

        self.session = requests.Session()

        timestamp = now.isoformat()
        requestor_ref = app_id

        # terminate any previous subscription just in case
        self.terminate_subscription(timestamp, requestor_ref)

        termination_time = (now + timedelta(hours=24)).isoformat()

        self.subscribe(timestamp, requestor_ref, 'http://bustimes.org/siri', f"""
            <SituationExchangeSubscriptionRequest>
                <SubscriptionIdentifier>{requestor_ref}</SubscriptionIdentifier>
                <SubscriberRef>{requestor_ref}</SubscriberRef>
                <InitialTerminationTime>{termination_time}</InitialTerminationTime>
                <IncrementalUpdates>true</IncrementalUpdates>
            </SituationExchangeRequest>
        """)

    def arriva(self, terminate):
        self.source = DataSource.objects.get(name='Arriva')

        if not terminate and cache.get('Heartbeat:HAConTest'):
            return  # received a heartbeat recently, no need to resubscribe

        now = timezone.localtime()

        self.session = requests.Session()

        timestamp = now.isoformat()
        requestor_ref = 'HAConToBusTimesET'

        # Access to the subscription endpoint is restricted to certain IP addresses,
        # so use a Digital Ocean floating IP address
        self.session.mount('http://', SourceAddressAdapter('10.16.0.6'))

        # terminate any previous subscription just in case
        self.terminate_subscription()

        termination_time = (now + timedelta(hours=24)).isoformat()

        # (re)subscribe
        if not terminate:
            self.subscribe(timestamp, requestor_ref, 'http://68.183.252.225/siri', f"""
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
            """)

    def handle(self, *args, **options):
        self.tfn('', options['terminate'])

        self.arriva(options['terminate'])
