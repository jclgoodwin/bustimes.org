import uuid
from datetime import datetime, timedelta, timezone

import requests
from django.core.cache import cache
from django.core.management.base import BaseCommand
from requests_toolbelt.adapters.source import SourceAddressAdapter

from ...models import SiriSubscription


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("source_address", type=str)
        parser.add_argument("consumer_address", type=str)

    def handle(self, source_address, consumer_address, *args, **options):
        endpoint = "https://obst-s2s.tfw.vix-its.com"
        requestor_ref = "TFW_Bustimes_VM"

        now = datetime.now(timezone.utc)
        stats = cache.get("tfw_status")
        if stats:
            if (now - stats[-1][0]) < timedelta(minutes=5):
                return

        session = requests.Session()
        session.mount("https://", SourceAddressAdapter(source_address))

        subscription = SiriSubscription.objects.get()
        consumer_address = f"{consumer_address}/siri/{subscription.uuid}"

        initial_termination_time = now + timedelta(hours=20) - timedelta(minutes=6)

        data = f"""<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
    <SubscriptionRequest>
        <RequestTimestamp>{now.isoformat()}</RequestTimestamp>
        <RequestorRef>{requestor_ref}</RequestorRef>
        <ConsumerAddress>{consumer_address}</ConsumerAddress>
        <VehicleMonitoringSubscriptionRequest>
            <SubscriptionIdentifier>{uuid.uuid4()}</SubscriptionIdentifier>
            <InitialTerminationTime>{initial_termination_time.isoformat()}</InitialTerminationTime>
            <VehicleMonitoringRequest>
                <RequestTimestamp>{now.isoformat()}</RequestTimestamp>
            </VehicleMonitoringRequest>
            <IncrementalUpdates>true</IncrementalUpdates>
            <UpdateInterval>PT30S</UpdateInterval>
        </VehicleMonitoringSubscriptionRequest>
        <SubscriptionContext>
            <HeartbeatInterval>PT5M</HeartbeatInterval>
        </SubscriptionContext>
    </SubscriptionRequest>
</Siri>"""

        session.post(
            endpoint,
            data=data,
            headers={"content-type": "text/xml"},
        )
