import requests
from django.core.management.base import BaseCommand
from ...models import Service, ServiceCode


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        session = requests.Session()
        for route in session.get('https://api.tfl.gov.uk/Line/Mode/bus/Route').json():
            stops = route['routeSections'][0]['originator']
            services = Service.objects.filter(stops=stops, line_name=route['name'], current=True).distinct()
            try:
                try:
                    service = services.get(region='L')
                except Service.DoesNotExist:
                    service = services.get(region__in=('L', 'SE'))
            except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
                print(route['name'], e)
                continue
            ServiceCode.objects.update_or_create(scheme='TfL', service=service, code=route['name'])
