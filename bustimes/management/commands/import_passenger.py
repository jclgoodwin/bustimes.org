"""Import timetable data "fresh from the cow" """

import os
from time import sleep
from urllib.parse import urljoin, urlparse

import bs4
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from requests import Session

from busstops.models import DataSource

from ...download_utils import write_file
from ...models import TimetableDataSource, Version
from .import_bod_timetables import clean_up, get_operator_ids, handle_file, logger
from .import_transxchange import Command as TransXChangeCommand


def get_version(source, dates, url):
    filename = os.path.basename(urlparse(url).path)
    path = os.path.join(settings.DATA_DIR, filename)

    if not os.path.exists(path):
        response = requests.get(url, stream=True)
        url = response.url  # in case there was a redirect
        filename = os.path.basename(urlparse(url).path)
        path = os.path.join(settings.DATA_DIR, filename)

        if not os.path.exists(path):
            write_file(path, response)

    return Version.objects.update_or_create(
        {
            "start_date": dates[0],
            "end_date": dates[1],
            "url": url,
        },
        source=source,
        name=filename,
    )


def get_versions(session, source):
    versions = []
    try:
        response = session.get(source.url, timeout=61)
    except requests.RequestException as e:
        logger.warning(f"{source.url} {e}")
        sleep(5)
        return
    if not response.ok:
        logger.warning(f"{source.url} {response}")
        sleep(5)
        return

    soup = bs4.BeautifulSoup(response.text, "lxml")

    for heading in soup.find_all("h3"):
        if " to " not in heading.text:
            continue

        dates = (
            heading.text.removeprefix("Current Data (").removesuffix(")").split(" to ")
        )
        assert len(dates) == 2

        for element in heading.next_siblings:
            if type(element) is not bs4.element.Tag:
                continue
            link = element.find("a")
            assert link.text == "Download TransXChange"
            url = urljoin(response.url, link.attrs["href"])
            assert "/txc" in url
            versions.append(get_version(source, dates, url))

            break

    return versions


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("operator_name", type=str, nargs="?")

    def handle(self, operator_name, *args, **options):
        command = TransXChangeCommand()
        command.set_up()

        session = Session()

        prefix = "https://data.discoverpassenger.com/operator"
        suffix = "/open-data"

        timetable_data_sources = TimetableDataSource.objects.filter(
            Q(url__startswith=prefix) | Q(url__endswith=suffix), active=True
        )
        if operator_name:
            timetable_data_sources = timetable_data_sources.filter(name=operator_name)

        for source in timetable_data_sources:
            versions = get_versions(session, source)

            if versions:
                prefix = versions[0][0].name.split("_")[0]
                prefix = f"{prefix}_"  # eg 'transdevblazefield_'
                for filename in os.listdir(settings.DATA_DIR):
                    if filename.startswith(prefix):
                        if not any(filename == version.name for version, _ in versions):
                            os.remove(os.path.join(settings.DATA_DIR, filename))
            else:
                sleep(2)
                continue

            new_versions = any(modified for _, modified in versions)

            command.source, _ = DataSource.objects.get_or_create(
                {"name": source.name}, url=source.url
            )
            command.source.source = source

            if new_versions or operator_name:
                logger.info(source.name)

                operators = list(source.operators.values_list("noc", flat=True))

                command.source.datetime = timezone.now()
                command.region_id = source.region_id
                command.service_ids = set()
                command.route_ids = set()
                command.garages = {}

                for version, modified in versions:  # newest first
                    if modified or operator_name:
                        logger.info(version)
                        command.version = version
                        handle_file(command, version.name, qualify_filename=True)

                clean_up(source, [command.source])

                operator_ids = get_operator_ids(command.source)
                logger.info(f"  {operator_ids}")

                foreign_operators = [o for o in operator_ids if o not in operators]
                logger.info(f"  {foreign_operators}")

            # even if there are no new versions, delete non-current
            old_versions = source.version_set.filter(
                ~Q(id__in=[version.id for version, _ in versions])
            )
            command.source.route_set.filter(
                version__in=old_versions, service__isnull=False
            ).update(service=None, version=None)
            old_versions = old_versions.delete()

            if not (new_versions or operator_name):
                if old_versions[0]:
                    logger.info(source.name)
                else:
                    sleep(2)
                    continue
            logger.info(f"  {old_versions=}")

            # mark old services as not current
            old_services = command.source.service_set.filter(current=True, route=None)
            logger.info(f"  old services: {old_services.update(current=False)}")

            if new_versions or operator_name or old_versions:
                if not (new_versions or operator_name):
                    remaining_services = command.source.service_set.filter(current=True)
                    command.service_ids = remaining_services.values_list(
                        "id", flat=True
                    )
                command.finish_services()

            command.source.save()
