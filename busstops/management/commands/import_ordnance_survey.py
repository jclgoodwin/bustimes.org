import os
import zipfile
import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings


class Command(BaseCommand):
    def handle_file(self, open_file):
        lines = (line.decode() for line in open_file)
        for row in csv.DictReader(lines, fieldnames=self.fieldnames):
            if 'Whitwell' in row['NAME1']:
                print(row)

    @transaction.atomic
    def handle(self, *args, **options):
        path = os.path.join(settings.DATA_DIR, 'opname_csv_gb.zip')
        with zipfile.ZipFile(path) as archive:
            with archive.open(os.path.join('DOC', 'OS_Open_Names_Header.csv'), 'r') as open_file:
                self.fieldnames = open_file.read().decode('utf-8-sig').strip().split(',')
            for path in archive.namelist():
                if path.startswith('DATA') and path.endswith('.csv'):
                    with archive.open(path, 'r') as open_file:
                        self.handle_file(open_file)
