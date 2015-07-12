import sys
import csv
from django.core.management.base import BaseCommand
from busstops.models import Locality


class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        for row in reader:
            print row
            child = Locality.objects.get(id=row[1])
            parent = Locality.objects.get(id=row[0])
            child.parent = parent
            child.save()
