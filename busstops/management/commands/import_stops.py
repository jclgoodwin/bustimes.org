import sys
import csv

from django.core.management.base import BaseCommand

from django.contrib.gis.geos import Point

from busstops.models import StopPoint, Locality, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        # StopPoint.objects.all().delete()

        reader = csv.reader(sys.stdin)
        next(reader, None)
        for row in reader:
            try:
                StopPoint.objects.create(
                    atco_code=row[0],
                    naptan_code=row[1],
                    common_name=row[4],
                    landmark=row[8],
                    street=row[10],
                    crossing=row[12],
                    indicator=row[14],
                    locality=Locality.objects.get(id=row[17]),
                    suburb=row[23],
                    latlong=Point(map(float, (row[29], row[30]))),
                    stop_type=row[31],
                    bus_stop_type=row[32],
                    timing_status=row[33],
                    town=row[21],
                    locality_centre=(row[25] == '1'),
                    active=(row[42] == 'act'),
                    admin_area=AdminArea.objects.get(id=row[37]),
                    bearing=row[16]
                    )
            except:
                print 'Skipped row: ' + str(row)
