from django.core.management.base import BaseCommand
from ...translinkni import translink_disruptions


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("api_key", type=str)

    def handle(self, api_key, *args, **options):
        translink_disruptions(api_key=api_key)
