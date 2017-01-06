"""
Usage:

    ./manage.py import_tfl_stops < data/tfl/bus-stops.csv
"""
import warnings
import requests
from titlecase import titlecase
from django.core.exceptions import MultipleObjectsReturned
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint, LiveSource


TFL = LiveSource.objects.get_or_create(name='TfL')[0]


class Command(ImportFromCSVCommand):

    @staticmethod
    def get_name(atco_code):
        """
        Given a stop's ATCO code, returns the best-formatted version of its common name from the
        TfL API
        """
        try:
            data = requests.get('https://api.tfl.gov.uk/StopPoint/%s' % atco_code).json()
            return data.get('commonName')
        except ValueError as error:
            warnings.warn('{} {}'.format(atco_code, error))

    def handle_row(self, row):
        if row['Naptan_Atco'] in (None, '', 'NONE'):
            return None

        try:
            stop = StopPoint.objects.get(pk=row['Naptan_Atco'])
        except StopPoint.DoesNotExist:
            try:
                stop = StopPoint.objects.get(pk__contains=row['Naptan_Atco'])
            except (StopPoint.DoesNotExist, MultipleObjectsReturned) as error:
                warnings.warn('{} {}'.format(error, row))
                return

        if row['Heading'] != '':
            stop.heading = row['Heading']
        stop.common_name = self.get_name(stop.atco_code) or stop.common_name

        if stop.street.isupper():
            stop.street = titlecase(stop.street)
        if stop.landmark.isupper():
            stop.landmark = titlecase(stop.landmark)

        stop.live_sources.add(TFL)

        stop.save()
