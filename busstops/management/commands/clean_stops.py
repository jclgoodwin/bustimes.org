"Tidy up the NaPTAN data."

from django.core.management.base import BaseCommand
from ...models import StopPoint

INDICATORS_TO_PROPER_CASE = (
    'opp',
    'adj',
    'at',
    'nr',
    'on',
    'o/s',
    'in',
    'behind',
    'before',
    'after',
    'N-bound',
    'NE-bound',
    'E-bound',
    'SE-bound',
    'S-bound',
    'SW-bound',
    'W-bound',
    'NW-bound',
)
INDICATORS_TO_REPLACE = {
    'opp ': 'opp',
    'opp.': 'opp',
    'opposite': 'opp',
    'opposite ': 'opp',
    'adjacent': 'adj',
    'near': 'nr',
    'at ': 'at',
    'before ': 'before',
    'outside': 'o/s',
    'outside ': 'o/s',
    'os': 'o/s',
    'N bound': 'N-bound',
    'N - bound': 'N-bound',
    'NE bound': 'NE-bound',
    'NE - bound': 'NE-bound',
    'E bound': 'E-bound',
    'E - bound': 'E-bound',
    'SE bound': 'SE-bound',
    'SE - bound': 'SE-bound',
    'S bound': 'S-bound',
    'S - bound': 'S-bound',
    'SW bound': 'SW-bound',
    'SW - bound': 'SW-bound',
    'W bound': 'W-bound',
    'W - bound': 'W-bound',
    'NW bound': 'NW-bound',
    'NW - bound': 'NW-bound',
    'nb': 'N-bound',
    'eb': 'E-bound',
    'sb': 'S-bound',
    'wb': 'W-bound',
    'northbound': 'N-bound',
    'north bound': 'N-bound',
    'northeastbound': 'NE-bound',
    'north east bound': 'NE-bound',
    'eastbound': 'E-bound',
    'east-bound': 'E-bound',
    'east bound': 'E-bound',
    'south east bound': 'SE-bound',
    'southbound': 'S-bound',
    'south bound': 'S-bound',
    'south west bound': 'SW-bound',
    'wbound': 'W-bound',
    'westbound': 'W-bound',
    'west bound': 'W-bound',
    'nwbound': 'NW-bound',
    'northwestbound': 'NW-bound',
    'northwest bound': 'NW-bound',
    'north west bound': 'NW-bound',
}


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
    def normalise_indicators():
        for indicator in INDICATORS_TO_PROPER_CASE:
            StopPoint.objects.filter(indicator__iexact=indicator).update(indicator=indicator)

        for indicator, replacement in INDICATORS_TO_REPLACE.iteritems():
            StopPoint.objects.filter(indicator__iexact=indicator).update(indicator=replacement)

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
        self.normalise_indicators()
        self.replace_backticks()
