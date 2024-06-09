import datetime
import multiprocessing
import zipfile
from functools import partial

from django.core.management.base import BaseCommand

from busstops.models import Service
from transxchange.txc import TransXChange


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("archives", nargs=1, type=str)

    def handle(self, *args, **options):
        pool = multiprocessing.Pool()

        for archive_name in options["archives"]:
            print(archive_name)

            archive = zipfile.ZipFile(archive_name)

            print(pool)

            start = datetime.datetime.now()
            foop = pool.map(
                partial(self.handle_xml_file, archive_name), archive.namelist()
            )
            print(f"  {foop}")
            print(datetime.datetime.now() - start)

            start = datetime.datetime.now()
            foop = [
                self.handle_xml_file(archive_name, file_name)
                for file_name in archive.namelist()
            ]
            print(f"  {foop}")
            print(datetime.datetime.now() - start)

    # def handle_file(self, file):
    #     archive = zipfile.ZipFile(file)
    #     except zipfile.BadZipfile:
    #         self.handle_xml_file(file)
    #     else:
    #         self.handle_archive(archive)

    # def handle_archive(self, archive):
    #     namelist = archive.namelist()

    #     with multiprocessing.Pool() as pool:
    #         pool.map(self.handle_file, (archive.open(filename) for filename in namelist))

    @staticmethod
    def handle_xml_file(archive_name, file_name):
        archive = zipfile.ZipFile(archive_name)
        open_file = archive.open(file_name)
        transxchange = TransXChange(open_file)

        for service_code, service in transxchange.services.items():
            s = Service.objects.filter(service_code=service_code)
        return s
