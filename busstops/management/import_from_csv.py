"""
Base classes for import_* commands
"""

from io import open
import csv
from django.core.management.base import BaseCommand


class ImportFromCSVCommand(BaseCommand):
    """
    Base class for commands for importing data from CSV files (via stdin)
    """

    input = 0
    encoding = 'cp1252'

    @staticmethod
    def to_camel_case(field_name):
        """
        Given a string like 'naptan_code', returns a string like 'NaptanCode'
        """
        return ''.join(s.title() for s in field_name.split('_'))

    def handle_row(self, row):
        """
        Given a row (a dictionary),
        probably creates an object and saves it in the database
        """
        raise NotImplementedError

    @staticmethod
    def process_rows(rows):
        return rows

    def handle(self, *args, **options):
        """
        Runs when the command is executed
        """
        with open(self.input, encoding=self.encoding) as input:
            rows = csv.DictReader(input)
            for row in self.process_rows(rows):
                self.handle_row(row)
