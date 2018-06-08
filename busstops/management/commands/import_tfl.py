import requests
from django.management.commands import BaseCommand


class Command(BaseCommand):
    def handle(self):
        session = requests.Session()
        print(session.get('https://api.tfl.gov.uk/Line/Mode/bus/Route').json())
