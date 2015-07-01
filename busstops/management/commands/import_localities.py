import sys
import csv

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from busstops.models import Locality, AdminArea, District

class Command(BaseCommand):

    def handle(self, *args, **options):
        # Locality.objects.all().delete()

        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        for row in reader:
            try:
                locality = Locality(
                    id=row[0],
                    name=row[1],
                    qualifier_name=row[5],
                    admin_area=AdminArea.objects.get(id=row[9]),
                    easting=row[13],
                    northing=row[14],
                    )
                district = row[10]
                if district != '310': # bogus value for nonexistent districts
                    locality.district = District.objects.get(id=district),
                locality.save()
            except:
                print 'Skipped row: ' + str(row)
