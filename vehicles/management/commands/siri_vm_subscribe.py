import uuid
from datetime import datetime, timedelta, timezone

import requests
from django.core.cache import cache
from django.core.management.base import BaseCommand
from requests_toolbelt.adapters.source import SourceAddressAdapter
from xmltodict import unparse

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

        if subscription.username and subscription.password:
            auth = requests.auth.HTTPBasicAuth(
                subscription.username, subscription.password
            )
        else:
            auth = None

        session = requests.Session()
        if source_address:
            session.mount("https://", SourceAddressAdapter(source_address))

        if terminate:
            data = unparse(
                {
                    "Siri": {
                        "@xmlns": "http://www.siri.org.uk/siri",
                        "@version": "1.3",
                        "TerminateSubscriptionRequest": {
                            "RequestTimestamp": now.isoformat(),
                            "RequestorRef": subscription.requestor_ref,
                            "SubscriptionRef": terminate,
                        },
                    }
                }
            )
            print(data)
            res = session.post(
                subscription.producer_url,
                data=data,
                headers={"content-type": "text/xml"},
                auth=auth,
            )
            print(res)
            print(res.text)
            return

        consumer_address = f"{consumer_address}/siri/{subscription.uuid}"

        initial_termination_time = now + timedelta(hours=20) - timedelta(minutes=6)

        data = unparse(
            {
                "Siri": {
                    "@xmlns": "http://www.siri.org.uk/siri",
                    "@version": "1.3",
                    "SubscriptionRequest": {
                        "RequestTimestamp": now.isoformat(),
                        "RequestorRef": subscription.requestor_ref,
                        "ConsumerAddress": consumer_address,
                        "VehicleMonitoringSubscriptionRequest": {
                            "SubscriptionIdentifier": uuid.uuid4(),
                            "InitialTerminationTime": initial_termination_time.isoformat(),
                            "VehicleMonitoringRequest": {
                                "RequestTimestamp": now.isoformat(),
                            },
                            "IncrementalUpdates": True,
                            "UpdateInterval": "PT30S",
                        },
                        "SubscriptionContext": {
                            "HeartbeatInterval": "PT5M",
                        },
                    },
                }
            },
            pretty=True,
            indent="    ",
        )

        print(data)
        res = session.post(
            subscription.producer_url,
            data=data,
            headers={"content-type": "text/xml"},
            auth=auth,
        )
        print(res)
        print(res.text)
