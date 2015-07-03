from django.core.management.base import BaseCommand
from busstops.models import StopPoint


class Command(BaseCommand):

    def remove_placeholders(self):
        """Replace some StopPoint field values like '---' with ''
        """

        placeholders = ('-', '--', '---', '*', 'TBA', 'unknown')
        attrs = ('street', 'crossing', 'landmark')

        for placeholder in placeholders:
            for attr in attrs:
                StopPoint.objects.filter(**{attr + '__iexact': placeholder}).update(**{attr: ''})


    def remove_stupid_indicators(self):
        """Remove StopPoint indicator values which are long numbers
        """
        StopPoint.objects.filter(indicator__startswith='220').update(indicator='')


    def replace_backticks(self):
        """Replace ` with ' in StopPoint fields
        """
        for attr in ('common_name', 'street', 'landmark', 'crossing'):
            for stop in StopPoint.objects.filter(landmark__contains='`'):
                value = getattr(stop, attr)
                value = value.replace('`', '\'')
                setattr(stop, attr, value)
                stop.save()


    def handle(self, *args, **options):
        self.remove_placeholders()
        self.remove_stupid_indicators()
        self.replace_backticks()

