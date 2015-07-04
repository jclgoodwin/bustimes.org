import sys
import csv

from django.core.management.base import BaseCommand

from busstops.models import Region, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        for row in csv.reader(sys.stdin):
            try:
                AdminArea.objects.create(
                    id=row[0],
                    atco_code=row[1],
                    name=row[2],
                    short_name=row[4],
                    country=row[6],
                    region=Region.objects.get(id=row[7]),
                    )
            except:
                print 'Skipped row: ' + str(row)
