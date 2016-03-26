"""
Usage:

    ./manage.py import_tfl_stops < data/tfl/bus-stops.csv
"""

from titlecase import titlecase

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import StopPoint


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        if row['Naptan_Atco'] in (None, '', 'NONE'):
            return None

        try:
            stop = StopPoint.objects.get(pk=row['Naptan_Atco'])
        except ObjectDoesNotExist:
            try:
                stop = StopPoint.objects.get(pk__contains=row['Naptan_Atco'])
            except (ObjectDoesNotExist, MultipleObjectsReturned) as e:
                print e, row
                return None

        if row['Heading'] != '':
            stop.heading = row['Heading']
        stop.tfl = True

        if stop.street.isupper():
            stop.street = titlecase(stop.street)
        if stop.landmark.isupper():
            stop.landmark = titlecase(stop.landmark)

        stop.save()
