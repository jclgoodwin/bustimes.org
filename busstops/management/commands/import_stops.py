"""
Usage:

    ./manage.py import_stops < Stops.csv

or:

    grep 2015- Stops.csv | ./manage.py import_stops
"""

import sys
import csv

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from busstops.models import StopPoint, Locality, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        rows = enumerate(csv.reader(sys.stdin))
        next(rows)

        for i, row in rows:
            if i % 10000 == 0:
                print "At line %d" % i
            StopPoint.objects.get_or_create(
                atco_code=row[0],
                defaults=dict(
                    naptan_code=row[1],
                    common_name=row[4].decode('latin1'),
                    landmark=row[8].decode('latin1'),
                    street=row[10].decode('latin1'),
                    crossing=row[12].decode('latin1'),
                    indicator=row[14].decode('latin1'),
                    locality=Locality.objects.get(id=row[17]),
                    suburb=row[23].decode('latin1'),
                    location=Point(int(row[27]), int(row[28]), srid=27700),
                    latlong=Point(float(row[29]), float(row[30]), srid=4326),
                    stop_type=row[31],
                    bus_stop_type=row[32],
                    timing_status=row[33],
                    town=row[21].decode('latin1'),
                    locality_centre=(row[25] == '1'),
                    active=(row[42] == 'act'),
                    admin_area=AdminArea.objects.get(id=row[37]),
                    bearing=row[16],
                    )
                )
