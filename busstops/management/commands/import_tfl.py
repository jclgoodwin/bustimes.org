import requests
from django.core.management.base import BaseCommand
from ...models import Service, ServiceCode


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        session = requests.Session()
        for route in session.get('https://api.tfl.gov.uk/Line/Mode/bus/Route').json():
            try:
                service = Service.objects.get(line_name=route['name'], region='L', current=True,
                                              stops=route['routeSections'][0]['originator'])
                ServiceCode.objects.update_or_create(scheme='TfL', service=service, code=route['name'])
            except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
                print(route['name'], e)
