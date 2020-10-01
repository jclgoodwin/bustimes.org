import os
import shutil
from ftplib import FTP
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('username', type=str)
        parser.add_argument('password', type=str)

    def do_files(self, ftp, files):
        for name in files:
            if not name.endswith('.zip'):
                continue
            details = files[name]
            version = details['modify']
            versioned_name = f"{version}_{name}"
            path = os.path.join(settings.TNDS_DIR, versioned_name)
            if os.path.exists(path):
                if os.path.getsize(path) == int(details['size']):
                    continue
            with open(path, 'wb') as open_file:
                ftp.retrbinary(f"RETR {name}", open_file.write)
            destination = os.path.join(settings.TNDS_DIR, name)
            shutil.copy(path, destination)
            self.changed_files.append(destination)

    def handle(self, username, password, *args, **options):
        host = "ftp.tnds.basemap.co.uk"
        ftp = FTP(host=host, user=username, passwd=password)

        self.changed_files = []

        # do the 'TNDSV2.5' version if possible
        ftp.cwd('TNDSV2.5')
        v2_files = {name: details for name, details in ftp.mlsd()}
        self.do_files(ftp, v2_files)

        # add any missing regions (NCSD)
        ftp.cwd('..')
        files = {name: details for name, details in ftp.mlsd() if name not in v2_files}
        self.do_files(ftp, files)

        ftp.quit()

        for file in self.changed_files:
            print(file)
            call_command('import_transxchange', file)
