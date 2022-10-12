from django.test import TestCase

from accounts.models import User
from bustimes.models import RouteLink

from .models import Service, StopPoint


class MergeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.service_a = Service.objects.create(
            line_name="129", description="Frankby Cemetery - Liscard"
        )
        cls.service_b = Service.objects.create(
            line_name="129", description="Frankby - Moreton - Liscard"
        )

        stop_a = StopPoint.objects.create(atco_code="2902", active=True)
        stop_b = StopPoint.objects.create(atco_code="2903", active=True)
        RouteLink.objects.create(
            from_stop=stop_a,
            to_stop=stop_b,
            service=cls.service_a,
            geometry="LINESTRING(1.2 51.1,1.1 51.2)",
        )
        RouteLink.objects.create(
            from_stop=stop_a,
            to_stop=stop_b,
            service=cls.service_b,
            geometry="LINESTRING(1.3 51.1,1.1 51.3)",
        )

        cls.staff_user = User.objects.create(
            username="josh", is_staff=True, is_superuser=True, email="j@example.com"
        )

    def test_merge(self):
        self.client.force_login(self.staff_user)

        self.client.post(
            "/admin/busstops/service/",
            {
                "action": "merge",
                "_selected_action": [self.service_a.id, self.service_a.id],
            },
        )

        response = self.client.get("/admin/busstops/service/")
        self.assertContains(
            response, "Merged &lt;QuerySet []&gt; into 129 - Frankby Cemetery - Liscard"
        )
