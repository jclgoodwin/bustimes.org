import sys
import csv

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from busstops.models import Locality, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        Locality.objects.all().delete()

        for row in csv.reader(sys.stdin):
            try:
                Locality.objects.create(
                    id=row[0],
                    name=row[1],
                    qualifier_name=row[5],
                    admin_area=AdminArea.objects.get(id=row[9]),
                    easting=row[13],
                    northing=row[14],
                    )
            except:
                print 'Skipped row: ' + str(row)
