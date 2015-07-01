import sys
import csv

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from busstops.models import District, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        District.objects.all().delete()

        for row in csv.reader(sys.stdin):
            try:
                District.objects.create(
                    id=row[0],
                    name=row[1],
                    admin_area=AdminArea.objects.get(id=row[3]),
                    )
            except:
                print 'Skipped row: ' + str(row)
