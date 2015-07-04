import sys
import csv

from django.core.management.base import BaseCommand

from busstops.models import Region

class Command(BaseCommand):

    def handle(self, *args, **options):
        for row in csv.reader(sys.stdin):
            try:
                Region.objects.create(id=row[0], name=row[1])
            except:
                print 'Skipped row: ' + str(row)
