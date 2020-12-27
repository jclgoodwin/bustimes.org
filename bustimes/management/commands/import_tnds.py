import os
import shutil
import boto3
from ftplib import FTP
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('username', type=str)
        parser.add_argument('password', type=str)

    def get_existing_file(self, key):
        for file in self.existing_files['Contents']:
            if file['Key'] == key:
                return file

    def do_files(self, files):
        for name in files:
            if not name.endswith('.zip'):
                continue

            details = files[name]
            version = details['modify']
            versioned_name = f"{version}_{name}"

            s3_key = f'TNDS/{versioned_name}'
            existing = self.get_existing_file(s3_key)
            print(name)

            if not existing or existing['Size'] != int(details['size']):
                path = os.path.join(settings.TNDS_DIR, name)

                if not os.path.exists(path) or os.path.getsize(path) != int(details['size']):
                    with open(path, 'wb') as open_file:
                        self.ftp.retrbinary(f"RETR {name}", open_file.write)
                print(s3_key)
                print(self.client.upload_file(path, 'bustimes-data', s3_key))

                self.changed_files.append(path)

    def handle(self, username, password, *args, **options):
        self.client = boto3.client('s3', endpoint_url='https://ams3.digitaloceanspaces.com')

        for filename in os.listdir(settings.TNDS_DIR):
            if '_' in filename:
                s3_key = f'TNDS/{filename}'
                existing = self.get_existing_file(s3_key)
                path = os.path.join(settings.TNDS_DIR, s3_key)
                if not existing or existing['Size'] != os.path.getsize(path):
                    print(s3_key)
                    print(self.client.upload_file(path, 'bustimes-data', s3_key))
                os.remove(path)

        self.existing_files = self.client.list_objects_v2(Bucket='bustimes-data')

        host = "ftp.tnds.basemap.co.uk"

        self.ftp = FTP(host=host, user=username, passwd=password)

        self.changed_files = []

        # do the 'TNDSV2.5' version if possible
        self.ftp.cwd('TNDSV2.5')
        print(self.ftp.mlsd())
        v2_files = {name: details for name, details in self.ftp.mlsd()}
        self.do_files(v2_files)

        # add any missing regions (NCSD)
        self.ftp.cwd('..')
        files = {name: details for name, details in self.ftp.mlsd() if name not in v2_files}
        self.do_files(files)

        self.ftp.quit()

        for file in self.changed_files:
            print(file)
            before = timezone.now()
            call_command('import_transxchange', file)
            print(timezone.now() - before)
