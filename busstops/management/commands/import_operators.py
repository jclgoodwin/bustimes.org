import sys
import csv

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from busstops.models import Operator

class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        for row in reader:
            try:
                id = row[0].replace('=', '').replace('\'', '')
                operator = Operator(
                    id=id,
                    public_name=row[1],
                    vehicle_mode=row[14],
                    parent=row[17]
                    )
                reference_name=row[2]
                license_name=row[3]
                if reference_name and reference_name != operator.public_name:
                    operator.reference_name = reference_name
                if license_name and license_name != operator.public_name and license_name != reference_name:
                    operator.reference_name = license_name
                operator.save()
            except:
                print 'Skipped row: ' + str(row)
