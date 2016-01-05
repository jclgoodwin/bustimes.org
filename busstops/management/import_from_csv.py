"""
Base classes for import_* commands
"""

import sys
import csv
from django.core.management.base import BaseCommand
from django.db import transaction


class ImportFromCSVCommand(BaseCommand):
    """
    Base class for commands for importing data from CSV files (via stdin)
    """

    input = sys.stdin

    @staticmethod
    def to_camel_case(field_name):
        """
        Given a string like 'naptan_code', returns a string like 'NaptanCode'
        """
        return ''.join([s.title() for s in field_name.split('_')])

    def handle_row(self, row):
        """
        Given a row (a dictionary),
        probably creates an object and saves it in the database
        """
        raise NotImplementedError

    @transaction.atomic
    def handle(self, *args, **options):
        """
        Runs when the command is executed
        """
        for row in csv.DictReader(self.input):
            try:
                self.handle_row(row)
            except Exception, error:
                print str(error)
                print row
