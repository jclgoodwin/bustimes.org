from mock import patch
from django.test import TestCase
from django.core.management import call_command


class TNDSTest(TestCase):
    @patch('ftplib.FTP', autospec=True)
    @patch('boto3.client', autospec=True)
    def test_import_tnds(self, boto3, ftp):

        call_command('import_tnds', 'u', 'p')

        boto3.assert_called_with('s3', endpoint_url='https://ams3.digitaloceanspaces.com')

        ftp.assert_called_with(host='ftp.tnds.basemap.co.uk', user='u', passwd='p')
