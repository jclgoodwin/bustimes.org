from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from busstops.models import DataSource

from ...utils import log_time_taken


class Command(BaseCommand):
    bucket_name = "bustimes-data"

    @staticmethod
    def add_arguments(parser):
        parser.add_argument("username", type=str)
        parser.add_argument("password", type=str)

    def list_files(self):
        files = [
            (name, details)
            for name, details in self.ftp.mlsd()
            if name.endswith(".zip") and name != "L.zip"
        ]
        files.sort(key=lambda item: int(item[1]["size"]))  # smallest files first
        return {name: details for name, details in files}

    def do_files(self, files):
        for name, details in files.items():
            self.do_file(name, details)

    def do_file(self, name, details):
        from botocore.errorfactory import ClientError

        version = details["modify"]  # 20201102164248
        versioned_name = f"{version}_{name}"

        source, _ = DataSource.objects.get_or_create(
            url=f"ftp://{self.ftp.host}/{name}"
        )

        s3_key = f"TNDS/{name}"
        versioned_s3_key = f"TNDS/{versioned_name}"
        try:
            existing = self.client.head_object(Bucket=self.bucket_name, Key=s3_key)
            etag = existing["ETag"]
        except ClientError:
            existing = None
            etag = None

        path = settings.TNDS_DIR / name

        if not path.exists() or path.stat().st_size != int(details["size"]):
            with open(path, "wb") as open_file:
                self.ftp.retrbinary(f"RETR {name}", open_file.write)

        if not existing or existing["ContentLength"] != details["size"]:
            print(self.client.upload_file(str(path), self.bucket_name, s3_key))
            new_etag = self.client.head_object(Bucket=self.bucket_name, Key=s3_key)[
                "ETag"
            ]

            if etag != new_etag:  # copy a versioned copy
                self.client.copy(
                    {
                        "Bucket": self.bucket_name,
                        "Key": s3_key,
                    },
                    Bucket=self.bucket_name,
                    Key=versioned_s3_key,
                )
                etag = new_etag

        if not etag or etag != source.sha1:
            source.sha1 = etag

            self.changed_files.append((path, source))

    def handle(self, username, password, *args, **options):
        import logging
        from ftplib import FTP

        import boto3

        logger = logging.getLogger(__name__)

        self.client = boto3.client(
            "s3", endpoint_url="https://ams3.digitaloceanspaces.com"
        )

        self.ftp = FTP(
            host="ftp.tnds.basemap.co.uk", user=username, passwd=password, timeout=120
        )

        self.changed_files = []

        # do the 'TNDSV2.5' version if possible
        self.ftp.cwd("TNDSV2.5")
        v2_files = self.list_files()
        self.do_files(v2_files)

        self.ftp.quit()

        for file, source in self.changed_files:
            logger.info(file.name)
            with log_time_taken(logger):
                call_command("import_transxchange", file)

            source.save(update_fields=["sha1"])
