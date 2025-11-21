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
        parser.add_argument("subscription_name", type=str)
        parser.add_argument("terminate", type=str, nargs="?")

    def handle(
        self,
        source_address,
        consumer_address,
        subscription_name,
        terminate=None,
        *args,
        **options,
    ):
        subscription = SiriSubscription.objects.get(name=subscription_name)
        assert subscription.producer_url

        now = datetime.now(timezone.utc)
        if not terminate:
            if stats := cache.get(subscription.get_status_key()):
                if (now - stats[-1][0]) < timedelta(minutes=5):
                    return
            else:
                print(f"no {subscription} history, subscribing")

        if subscription.auth:
            auth = requests.auth.HTTPBasicAuth("user", "pass")
        else:
            auth = None

        session = requests.Session(auth=auth)
        if source_address:
            session.mount("https://", SourceAddressAdapter(source_address))

        if terminate:
            data = f"""<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
    <TerminateSubscriptionRequest>
        <RequestTimestamp>{now.isoformat()}</RequestTimestamp>
        <RequestorRef>{subscription.requestor_ref}</RequestorRef>
        <SubscriptionRef>{terminate}</SubscriptionRef>
    </TerminateSubscriptionRequest>
</Siri>"""
            print(data)
            res = session.post(
                subscription.producer_url,
                data=data,
                headers={"content-type": "text/xml"},
            )
            print(res.text)
            return

        consumer_address = f"{consumer_address}/siri/{subscription.uuid}"

        initial_termination_time = now + timedelta(hours=20) - timedelta(minutes=6)

        data = f"""<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
    <SubscriptionRequest>
        <RequestTimestamp>{now.isoformat()}</RequestTimestamp>
        <RequestorRef>{subscription.requestor_ref}</RequestorRef>
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
            subscription.producer_url,
            data=data,
            headers={"content-type": "text/xml"},
        )
