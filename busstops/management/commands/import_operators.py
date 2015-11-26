"""
Usage:

    ./manage.py import_operators < NOC_db.csv
"""
import sys
import csv
from django.core.management.base import BaseCommand
from busstops.models import Operator, Region

class Command(BaseCommand):

    @staticmethod
    def row_to_operator(row):
        "Given a CSV row (a list), returns an Operator object"
        id = row[0].replace('=', '')
        region_id = row[12].replace('Admin', 'GB').replace('ADMIN', 'GB').replace('SC', 'S').replace('YO', 'Y').replace('WA', 'W').replace('LO', 'L')
        region = Region.objects.get(id=region_id)

        if row[1] in ('First', 'Arriva', 'Stagecoach') or row[1].startswith('inc.') or row[1].startswith('formerly'):
            name = row[2]  # OperatorReferenceName
        else:
            name = row[1]  # OperatorPublicName

        name = name.replace('\'', u'\u2019') # Fancy apostrophe

        operator = Operator.objects.update_or_create(
            id=id,
            defaults=dict(
                name=name.strip(),
                vehicle_mode=row[13].lower().replace('ct operator', 'community transport'),
                parent=row[16].strip(),
                region=region,
                )
            )[0]
        return operator

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader)  # skip past header
        for row in reader:
            if row[0] not in ('CECT'):
                operator = self.row_to_operator(row)
                operator.save()
