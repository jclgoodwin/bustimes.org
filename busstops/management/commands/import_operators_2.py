import os
import csv
# from pathlib import Path
# from datetime import datetime

from django.conf import settings
from django.core.management import BaseCommand

from bustimes.utils import download_if_changed
from ...models import Operator


# def parse_date(date_string):
#     if date_string:
#         return datetime.strptime(date_string, '%d/%m/%y').date()


# def download_if_modified(path):
#     url = f"https://content.mgmt.dvsacloud.uk/olcs.prod.dvsa.aws/data-gov-uk-export/{path}"
#     path = os.path.join(settings.DATA_DIR, path)
#     return download_if_changed(path, url)


def get_region_id(region_id):
    if region_id in {'ADMIN', 'Admin', 'Taxi', ''}:
        return 'GB'
    elif region_id in {'SC', 'YO', 'WA', 'LO'}:
        return region_id[0]
    return region_id


class Command(BaseCommand):
    def get_rows(self, path):
        with open(path) as open_file:
            for line in csv.DictReader(open_file):
                yield line

    def handle(self, **kwargs):
        url = 'https://mytraveline.info/NOC/NOC_DB.csv'
        path = settings.DATA_DIR / 'NOC_DB.csv'
        modified, last_modified = download_if_changed(path, url)

        print(modified, last_modified)

        operators = Operator.objects.in_bulk()
        # print(operators)

        to_update = []

        for row in self.get_rows(path):
            noc = row['NOCCODE']

            if len(noc) < 3:
                continue
            # if row['Date Ceased'] and noc in operators:
            #     print(row)

            # if noc not in operators:
            #     print(row)

            if noc in operators:
                operator = operators[noc]
                to_update.append(operator)
            else:
                operator = Operator(
                    region_id=get_region_id(row['TLRegOwn'])
                )

            operator.name = row['OperatorPublicName']

            if not operator.id:
                operator.id = noc
                operator.save()

        Operator.objects.bulk_update(to_update, ['name'])
