from django.contrib.admin import site
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from bustimes.models import Route, RouteLink

from .models import DataSource, Service, StopPoint


class BusStopsAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = DataSource.objects.create()

        cls.service_a = Service.objects.create(
            line_name="129", description="Frankby Cemetery - Liscard"
        )
        cls.service_b = Service.objects.create(
            line_name="129A", description="Frankby - Moreton - Liscard"
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
        Route.objects.create(
            source=cls.source,
            service_code="129",
            code="129",
            line_name="129",
            service=cls.service_a,
        )
        Route.objects.create(
            source=cls.source,
            service_code="129",
            code="129A",
            line_name="129A",
            service=cls.service_b,
        )

        cls.staff_user = User.objects.create(
            username="josh", is_staff=True, is_superuser=True, email="j@example.com"
        )

    def make_url(self, site, model, page: str) -> str:
        return reverse(
            f"{site.name}:{model._meta.app_label}_{model._meta.model_name}_{page}"
        )

    def test_everything(self):
        self.client.force_login(self.staff_user)

        for model, model_admin in site._registry.items():
            url = self.make_url(site, model, "changelist")
            response = self.client.get(url, {"q": "blah"})
            self.assertEqual(response.status_code, 200)

            url = self.make_url(site, model, "add")
            response = self.client.get(url, {"q": "blah"})
            self.assertEqual(response.status_code, 200)

    def test_merge_and_unmerge(self):
        self.client.force_login(self.staff_user)

        self.client.post(
            "/admin/busstops/service/",
            {
                "action": "merge",
                "_selected_action": [self.service_a.id, self.service_b.id],
            },
        )
        response = self.client.get("/admin/busstops/service/")
        self.assertEqual(
            list(response.context["messages"])[0].message,
            "merged <QuerySet [<Service: 129A - Frankby - Moreton - Liscard>]> into 129 - Frankby Cemetery - Liscard",
        )

        # merged into 1:
        self.assertEqual(Service.objects.count(), 1)

        # unmerge back into 2:
        self.client.post(
            "/admin/busstops/service/",
            {
                "action": "unmerge",
                "_selected_action": [self.service_a.id],
            },
        )
        self.assertEqual(Service.objects.count(), 2)

    def test_split_service_filter(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            "/admin/busstops/service/?split=1",
        )
        self.assertContains(response, "Frankby Cemetery - Liscard")

    def test_data_source_admin(self):
        url = "/admin/busstops/datasource/"

        self.client.force_login(self.staff_user)
        response = self.client.get(url)
        self.assertContains(response, ">0<")  # services
        self.assertContains(response, ">2<")  # routes

        self.client.post(
            url,
            {
                "action": "delete_routes",
                "_selected_action": [self.source.id],
            },
        )
        response = self.client.get(url)

        with self.assertNumQueries(4):
            self.client.post(
                url,
                {
                    "action": "remove_datetimes",
                    "_selected_action": [self.source.id],
                },
            )
