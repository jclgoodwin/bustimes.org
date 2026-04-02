import requests
from django.core.management.base import BaseCommand


from vehicles.models import get_text_colour
from ...models import DataSource, ServiceColour, Service


class Command(BaseCommand):
    def handle(self, *args, **options):
        source, _ = DataSource.objects.get_or_create(name="jersey")

        response = requests.get(
            "http://sojbuslivetimespublic.azurewebsites.net/api/Values/v1/GetRoutes"
        )
        routes = response.json()["routes"]

        for item in routes:
            colour = item["Colour"]
            colour, _ = ServiceColour.objects.get_or_create(
                {"name": item["Number"]},
                background=colour,
                foreground=get_text_colour(colour) or "#000",
            )

            service, _ = Service.objects.update_or_create(
                {
                    "colour": colour,
                    "description": item["Name"].strip(),
                    "current": True,
                    "region_id": "JE",
                },
                line_name=item["Number"],
                source=source,
            )

            service.operator.set(["libertybus"])
