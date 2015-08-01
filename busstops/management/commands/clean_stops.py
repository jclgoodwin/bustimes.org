"Tidy up the NaPTAN data."

from django.core.management.base import BaseCommand
from busstops.models import StopPoint


class Command(BaseCommand):
    """
    Command that tidies the StopPoint objects in the database
    (because the NaPTAN data is a bit messy).

    In general, I could use certain heuristics to make this quicker
    (different local authorities seem to do different things wrong)
    but I'm not doing so yet.

    It might also be better to build this into the import process,
    or otherwise pre-process the CSV file.
    """

    @staticmethod
    def remove_placeholders():
        "Replace some StopPoint field values like '---' with ''"

        attrs = ('street', 'crossing', 'landmark', 'indicator')
        placeholders = ('-', '--', '---', '*', 'TBA', 'unknown')

        for placeholder in placeholders:
            for attr in attrs:
                StopPoint.objects.filter(**{attr + '__iexact': placeholder}).update(**{attr: ''})

    @staticmethod
    def remove_stupid_indicators():
        "Remove StopPoint indicator values which are long numbers."
        StopPoint.objects.filter(indicator__startswith='220').update(indicator='')

    @staticmethod
    def replace_backticks():
        "Replace ` with ' in StopPoint fields"
        for attr in ('common_name', 'street', 'landmark', 'crossing'):
            for stop in StopPoint.objects.filter(**{attr + '__contains': '`'}):
                value = getattr(stop, attr)
                value = value.replace('`', '\'')
                setattr(stop, attr, value)
                stop.save()


    def handle(self, *args, **options):
        self.remove_placeholders()
        self.remove_stupid_indicators()
        self.replace_backticks()

