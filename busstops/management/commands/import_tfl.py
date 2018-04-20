# import warnings
import requests
# from titlecase import titlecase
# from django.core.exceptions import MultipleObjectsReturned
from django.management.commands import BaseCommand
# from ...models import LiveSource


class Command(BaseCommand):
    def handle(self):
        session = requests.Session()
        print(session.get('https://api.tfl.gov.uk/Line/Mode/bus/Route').json())
