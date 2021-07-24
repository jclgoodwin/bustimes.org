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

    def list_files(self):
        files = [(name, details) for name, details in self.ftp.mlsd() if name.endswith('.zip')]
        files.sort(key=lambda item: int(item[1]['size']))  # smallest files first
        return {
            name: details for name, details in files
        }

    def do_files(self, files):
        for name in files:
            details = files[name]
            version = details['modify']
            versioned_name = f"{version}_{name}"

            s3_key = f'TNDS/{versioned_name}'
            existing = self.get_existing_file(s3_key)

            if existing and existing['Size'] == int(details['size']):
                continue

            path = settings.TNDS_DIR / name
            if path.exists() and path.stat().st_size == int(details['size']):
                continue

            with open(path, 'wb') as open_file:
                self.ftp.retrbinary(f"RETR {name}", open_file.write)
            self.client.upload_file(str(path), 'bustimes-data', s3_key)

            self.changed_files.append(path)

    def handle(self, username, password, *args, **options):
        self.client = boto3.client('s3', endpoint_url='https://ams3.digitaloceanspaces.com')

        self.existing_files = self.client.list_objects_v2(Bucket='bustimes-data')

        host = "ftp.tnds.basemap.co.uk"

        self.ftp = FTP(host=host, user=username, passwd=password)

        self.changed_files = []

        # do the 'TNDSV2.5' version if possible
        self.ftp.cwd('TNDSV2.5')
        v2_files = self.list_files()
        self.do_files(v2_files)

        # add any missing regions (NCSD)
        self.ftp.cwd('..')
        files = self.list_files()
        files = {name: files[name] for name in files if name not in v2_files}
        self.do_files(files)

        self.ftp.quit()

        for file in self.changed_files:
            print(file)
            before = timezone.now()
            call_command('import_transxchange', file)
            print(timezone.now() - before)
