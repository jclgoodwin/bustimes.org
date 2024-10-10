from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from vcr import use_cassette

from busstops.models import DataSource, Operator, Region

from ...models import Route, TimetableDataSource


class ImportPassengerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        sw = Region.objects.create(pk="SW", name="South West")
        Operator.objects.create(noc="BLUS", region=sw, name="Bluestar")
        Operator.objects.create(noc="UNIL", region=sw, name="Unilink")

    def test_import(self):
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        TimetableDataSource.objects.create(
            active=True,
            url="https://data.discoverpassenger.com/operator/unilink",
            name="Unilink",
        )

        with (
            override_settings(DATA_DIR=fixtures_dir),
            use_cassette(
                str(fixtures_dir / "passenger.yaml"), decode_compressed_response=True
            ),
            patch("bustimes.management.commands.import_passenger.write_file"),
            self.assertRaises(FileNotFoundError),
            self.assertLogs("bustimes.management.commands.import_bod_timetables") as cm,
        ):
            call_command("import_passenger")

        self.assertEqual(
            cm.output,
            [
                "INFO:bustimes.management.commands.import_bod_timetables:Unilink",
                "INFO:bustimes.management.commands.import_bod_timetables:{"
                "'dates': ['2022-03-27', '2022-04-24'], "
                "'url': 'https://s3-eu-west-1.amazonaws.com/passenger-sources/unilink/txc/unilink_1648047602.zip', "
                "'filename': 'unilink_1648047602.zip', 'modified': True}",
            ],
        )

        self.assertFalse(Route.objects.all())

        source = DataSource.objects.get()
        route = Route(
            code="gocornwallbus_1653042367.zip/TXC Export 20220520-1013.xml#SER23"
        )
        # date from timestamp in code (1653042367)
        self.assertEqual(
            source.credit(route),
            """<a href="https://data.discoverpassenger.com/operator/unilink" rel="nofollow">Unilink</a>, """
            + """<time datetime="2022-05-20">20 May 2022</time>""",
        )
