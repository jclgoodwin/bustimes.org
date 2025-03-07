from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import fakeredis
import time_machine
from django.core.management import call_command
from django.test import TestCase, override_settings
from vcr import use_cassette

from busstops.models import DataSource

from ...models import SiriSubscription, Vehicle


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class SiriPostTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(name="Transport for Wales")
        SiriSubscription.objects.create(
            name="Transport for Wales", uuid="475d1d1f-5708-4ee1-8f51-c63d948bc0b9"
        )

    @time_machine.travel("2023-12-15T08:24:05Z")
    def test_subscribe(self):
        vcr_dir = Path(__file__).resolve().parent / "vcr"

        with use_cassette(str(vcr_dir / "siri_vm_subscribe.yaml")):
            with mock.patch(
                "vehicles.management.commands.siri_vm_subscribe.cache.get",
                return_value=[[datetime(2023, 12, 15, 8, 20, tzinfo=timezone.utc)]],
            ):
                call_command("siri_vm_subscribe", "198.51.100.0", "http://example.com")

            call_command("siri_vm_subscribe", "198.51.100.0", "http://example.com")

    def test_siri_post_404(self):
        response = self.client.post("/siri/7e491d62-e9de-44eb-b197-ab0419bb033d")
        self.assertEqual(404, response.status_code)

    def test_siri_post_heartbeat(self):
        response = self.client.post(
            "/siri/475d1d1f-5708-4ee1-8f51-c63d948bc0b9",
            data="""<?xml version="1.0" encoding="UTF-8" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.siri.org.uk/siri http://www.siri.org.uk/schema/1.3/siri.xsd">
    <HeartbeatNotification>
        <RequestTimestamp>2023-11-30T13:14:01+00:00</RequestTimestamp>
        <ProducerRef>Beluga</ProducerRef>
        <Status>true</Status>
        <ServiceStartedTime>2023-11-29T09:43:26+00:00</ServiceStartedTime>
    </HeartbeatNotification>
</Siri>""",
            content_type="text/xml",
        )
        self.assertEqual(200, response.status_code)

    @time_machine.travel("2023-12-15T08:24:05Z")
    def test_siri_post_data(self):
        redis_client = fakeredis.FakeStrictRedis(version=7)

        data = """<?xml version="1.0" encoding="UTF-8" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.siri.org.uk/siri http://www.siri.org.uk/schema/1.3/siri.xsd">
    <ServiceDelivery>
        <ResponseTimestamp>2024-03-15T06:09:42+00:00</ResponseTimestamp>
        <VehicleMonitoringDelivery>
            <SubscriptionRef>a80aac8a-29fa-42fe-9487-683a412b5c1f</SubscriptionRef>
            <VehicleActivity>
                <ItemIdentifier>TFW_BUSTIMES_VM:VEHICLESTATUSRT:1372:0</ItemIdentifier>
                <RecordedAtTime>2024-03-15T06:09:42+00:00</RecordedAtTime>
                <ValidUntilTime>2024-03-15T06:09:42+00:00</ValidUntilTime>
                <VehicleMonitoringRef>NADT-MB181</VehicleMonitoringRef>
                <MonitoredVehicleJourney>
                    <Bearing>0</Bearing>
                    <InPanic>false</InPanic>
                    <BlockRef>Unknown</BlockRef>
                    <Monitored>false</Monitored>
                    <VehicleRef>NADT-MB181</VehicleRef>
                    <OperatorRef>NADT</OperatorRef>
                    <VehicleLocation>
                        <Latitude>51.3869667</Latitude>
                        <Longitude>-3.3494811</Longitude>
                    </VehicleLocation>
                    <VehicleFeatureRef>lowFloor</VehicleFeatureRef>
                    <FramedVehicleJourneyRef>
                        <DataFrameRef>2024-03-15</DataFrameRef>
                        <DatedVehicleJourneyRef>UNKNOWN</DatedVehicleJourneyRef>
                    </FramedVehicleJourneyRef>
                </MonitoredVehicleJourney>
            </VehicleActivity>
        </VehicleMonitoringDelivery>
    </ServiceDelivery>
</Siri>"""

        with (
            mock.patch(
                "vehicles.management.import_live_vehicles.redis_client", redis_client
            ),
            mock.patch(
                "vehicles.management.commands.import_bod_avl.redis_client", redis_client
            ),
        ):
            response = self.client.post(
                "/siri/475d1d1f-5708-4ee1-8f51-c63d948bc0b9",
                data=data,
                content_type="text/xml",
            )
            self.assertEqual(200, response.status_code)

        vehicle = Vehicle.objects.get()
        self.assertEqual(str(vehicle), "MB181")

        response = self.client.get("/siri/475d1d1f-5708-4ee1-8f51-c63d948bc0b9")
        self.assertEqual(response.headers["Content-Type"], "text/xml")
