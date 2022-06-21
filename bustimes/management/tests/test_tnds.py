import time_machine
from unittest import mock
from tempfile import TemporaryDirectory
from pathlib import Path
from django.test import TestCase, override_settings
from django.core.management import call_command


class TNDSTest(TestCase):
    @mock.patch("bustimes.management.commands.import_tnds.call_command")
    @mock.patch("ftplib.FTP", autospec=True)
    @mock.patch("boto3.client", autospec=True)
    def test_import_tnds(self, boto3, ftp, mock_call_command):

        ftp.return_value.mlsd = mock.Mock(
            return_value=[
                (
                    "EA.zip",
                    {"type": "file", "modify": "20210719162822", "size": "4879294"},
                ),
                (
                    "EM.zip",
                    {"type": "file", "modify": "20210719162823", "size": "21222664"},
                ),
                (
                    "IOM.zip",
                    {"type": "file", "modify": "20210719162823", "size": "501649"},
                ),
            ]
        )

        with time_machine.travel("2021-01-01", tick=False):
            with self.assertLogs("bustimes.management.commands.import_tnds") as cm:
                with TemporaryDirectory() as directory:
                    with override_settings(TNDS_DIR=Path(directory)):
                        call_command("import_tnds", "u", "p")

        self.assertEqual(
            cm.output,
            [
                "INFO:bustimes.management.commands.import_tnds:IOM.zip",
                "INFO:bustimes.management.commands.import_tnds:0:00:00",
                "INFO:bustimes.management.commands.import_tnds:EA.zip",
                "INFO:bustimes.management.commands.import_tnds:0:00:00",
                "INFO:bustimes.management.commands.import_tnds:EM.zip",
                "INFO:bustimes.management.commands.import_tnds:0:00:00",
            ],
        )

        boto3.assert_called_with(
            "s3", endpoint_url="https://ams3.digitaloceanspaces.com"
        )

        ftp.assert_called_with(host="ftp.tnds.basemap.co.uk", user="u", passwd="p")

        mock_call_command.assert_called()
