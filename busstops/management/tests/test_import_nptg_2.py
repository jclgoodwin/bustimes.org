from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command
# from .. import import_from_csv
# from ..commands import (import_regions, import_areas, import_districts, import_localities, import_locality_hierarchy,
#                         import_adjacent_localities)
from ...models import Region, AdminArea, District, Locality, StopPoint


class ImportNPTGTest(TestCase):
    def test_import_nptg(self):
        with patch(
            'busstops.management.commands.import_nptg.download_if_changed', return_value=(True, None)
        ) as mocked_download:
            with self.assertNumQueries(6):
                call_command('import_nptg')

            with self.assertNumQueries(6):
                call_command('import_nptg')

        print(mocked_download.calls)

        self.assertEqual(Region.objects.all().count(), 12)
