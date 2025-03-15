"""Import timetable data "fresh from the cow" """

import hashlib
import logging
import xml.etree.cElementTree as ET
import zipfile
from pathlib import Path
from time import sleep

import requests
from ciso8601 import parse_datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import DataError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from busstops.models import DataSource, Operator, Service

from ...download_utils import download, download_if_modified
from ...models import Route, TimetableDataSource
from ...utils import log_time_taken
from .import_transxchange import Command as TransXChangeCommand

logger = logging.getLogger(__name__)


def clean_up(timetable_data_source, sources, incomplete=False):
    service_operators = Service.operator.through.objects.filter(
        service=OuterRef("service")
    )
    operators = timetable_data_source.operators.values_list("noc", flat=True)

    routes = Route.objects.filter(
        ~Q(source__in=sources),
        Q(source__source=timetable_data_source)
        | Q(
            ~Q(source__name__in=("L", "bustimes.org")),
            Exists(service_operators.filter(operator__in=operators)),
            ~Exists(
                service_operators.filter(~Q(operator__in=operators))
            ),  # exclude joint services
        ),
    )
    if incomplete:  # leave other sources alone
        routes = routes.filter(source__url__contains="bus-data.dft.gov.uk")
    # force evaluation of QuerySet:
    route_ids = list(routes.values_list("id", flat=True))
    routes = Route.objects.filter(id__in=route_ids)
    # do this first to prevent IntegrityError
    routes.update(service=None)
    # routes.delete()
    Service.objects.filter(
        ~Q(source__name="bustimes.org"),
        operator__in=operators,
        current=True,
        route=None,
    ).update(current=False)


def is_noc(search_term: str) -> bool:
    assert str
    return len(search_term) <= 4 and search_term.isupper()


def get_operator_ids(source) -> list:
    operators = (
        Operator.objects.filter(service__route__source=source).distinct().values("noc")
    )
    return [operator["noc"] for operator in operators]


def get_command():
    command = TransXChangeCommand()
    command.set_up()
    return command


def get_sha1(path):
    sha1 = hashlib.sha1()
    with path.open("rb") as open_file:
        while True:
            data = open_file.read(65536)
            if not data:
                return sha1.hexdigest()
            sha1.update(data)


def handle_file(command, path, qualify_filename=False):
    # the downloaded file might be plain XML, or a zipped archive - we just don't know yet
    full_path = settings.DATA_DIR / path

    try:
        with zipfile.ZipFile(full_path) as archive:
            for filename in archive.namelist():
                if filename.endswith(".csv") or "__MACOSX/" in filename:
                    continue
                with archive.open(filename) as open_file:
                    if qualify_filename:
                        # source has multiple versions (Passsenger) so add a prefix like 'gonortheast_123.zip/'
                        filename = str(Path(path) / filename)
                    try:
                        command.handle_file(open_file, filename)
                    except (ET.ParseError, ValueError, AttributeError, DataError) as e:
                        if filename.endswith(".xml"):
                            logger.info(filename)
                            logger.exception(e)
    except zipfile.BadZipFile:
        # plain XML
        with full_path.open() as open_file:
            if qualify_filename:
                filename = path
            else:
                filename = ""
            try:
                command.handle_file(open_file, filename)
            except (AttributeError, DataError) as e:
                logger.exception(e)


def get_bus_open_data_paramses(sources, api_key):
    searches = [
        source.search for source in sources if not is_noc(source.search)
    ]  # e.g. 'TM Travel'
    nocs = [source.search for source in sources if is_noc(source.search)]  # e.g. 'TMTL'

    # chunk – we will search for nocs 20 at a time
    nocses = [nocs[i : i + 20] for i in range(0, len(nocs), 20)]

    base_params = {
        "api_key": api_key,
        "status": "published",
        "limit": 100,
    }

    # and search phrases one at a time
    for search in searches:
        yield {
            **base_params,
            "search": search,
        }

    for nocs in nocses:
        yield {**base_params, "noc": ",".join(nocs)}


def bus_open_data(api_key, specific_operator):
    assert len(api_key) == 40

    command = get_command()

    session = requests.Session()

    url_prefix = "https://data.bus-data.dft.gov.uk"
    path_prefix = settings.DATA_DIR / "bod"
    if not path_prefix.exists():
        path_prefix.mkdir()

    datasets = []

    timetable_data_sources = TimetableDataSource.objects.filter(
        ~Q(search=""), url="", active=True
    )
    if specific_operator:
        timetable_data_sources = timetable_data_sources.filter(name=specific_operator)
        if not timetable_data_sources:
            logger.info(f"no timetable data sources named {specific_operator}")
            return
        logger.info(timetable_data_sources)

    for params in get_bus_open_data_paramses(timetable_data_sources, api_key):
        url = f"{url_prefix}/api/v1/dataset/"
        while url:
            response = session.get(url, params=params)
            assert response.ok
            json = response.json()
            results = json["results"]
            if not results:
                logger.warning(f"no results: {response.url}")
            for dataset in results:
                dataset["modified"] = parse_datetime(dataset["modified"])
                datasets.append(dataset)
            url = json["next"]
            params = None

    all_source_ids = []

    for source in timetable_data_sources:
        if not is_noc(source.search):
            operator_datasets = [
                item
                for item in datasets
                if source.search in item["name"] or source.search in item["description"]
            ]
        else:
            operator_datasets = [
                item for item in datasets if source.search in item["noc"]
            ]

        command.region_id = source.region_id

        sources = []
        service_ids = set()

        operators = source.operators.values_list("noc", flat=True)

        for dataset in operator_datasets:
            command.source = DataSource.objects.filter(url=dataset["url"]).first()
            if (
                not command.source
                and is_noc(source.search)
                and len(operator_datasets) == 1
            ):
                name_prefix = dataset["name"].split("_", 1)[0]
                # if old dataset was made inactive, reuse id
                command.source = DataSource.objects.filter(
                    name__startswith=f"{name_prefix}_"
                ).first()
            if not command.source:
                command.source = DataSource.objects.create(
                    name=dataset["name"], url=dataset["url"]
                )
            command.source.name = dataset["name"]
            command.source.url = dataset["url"]
            if command.source.source_id != source.id:
                command.source.source = source
                if command.source.id:
                    command.source.save(update_fields=["source"])

            sources.append(command.source)

            if specific_operator or command.source.datetime != dataset["modified"]:
                logger.info(dataset["name"])

                filename = str(command.source.id)
                path = path_prefix / filename

                command.service_ids = set()
                command.route_ids = set()
                command.garages = {}

                command.source.datetime = dataset["modified"]

                with log_time_taken(logger):
                    download(path, url=command.source.url, session=session)

                    handle_file(command, path)

                    command.mark_old_services_as_not_current()

                    command.source.sha1 = get_sha1(path)
                    command.source.save()

                operator_ids = get_operator_ids(command.source)
                logger.info(f"  {operator_ids}")
                unexpected = [o for o in operator_ids if o not in operators]
                if unexpected:
                    logger.info(f"  {unexpected=} (not in {operators})")

                service_ids |= command.service_ids

        # delete routes from any sources that have been made inactive
        if Service.objects.filter(
            Q(source__in=sources) | Q(route__source__in=sources),
            current=True,
        ).exists():
            clean_up(source, sources, not source.complete)
        elif Service.objects.filter(
            current=True,
            route__source__source=source,
        ).exists():
            logger.warning(
                f"""{operators} has no current data
https://bustimes.org/admin/busstops/service/?operator__noc__in={",".join(operators)}"""
            )

        command.service_ids = service_ids
        command.finish_services()
        all_source_ids += [source.id for source in sources]

    if not specific_operator:
        to_delete = DataSource.objects.filter(
            ~Q(id__in=all_source_ids),
            ~Exists(Route.objects.filter(source=OuterRef("id"))),
            url__startswith=f"{url_prefix}/timetable/",
        )
        if to_delete:
            logger.info(to_delete)
            for source in to_delete:  # one by one to use less memory
                source.delete()


def ticketer(specific_operator=None):
    command = get_command()

    session = requests.Session()

    base_dir = settings.DATA_DIR / "ticketer"

    if not base_dir.exists():
        base_dir.mkdir()

    timetable_data_sources = TimetableDataSource.objects.filter(
        url__startswith="https://opendata.ticketer.com", active=True
    )
    if specific_operator:
        timetable_data_sources = timetable_data_sources.filter(
            operators=specific_operator
        )
        if not timetable_data_sources:
            logger.info(f"no timetable data sources for noc {specific_operator}")
            return
        logger.info(timetable_data_sources)

    need_to_sleep = False

    for source in timetable_data_sources:
        path = Path(source.url)

        filename = f"{path.parts[3]}.zip"
        path = base_dir / filename
        command.source, created = DataSource.objects.get_or_create(
            {"name": source.name}, url=source.url
        )
        command.source.source = source
        command.garages = {}

        if need_to_sleep:
            sleep(2)
            need_to_sleep = False

        modified, last_modified = download_if_modified(path, command.source, session)

        if (
            specific_operator
            or not command.source.datetime
            or last_modified > command.source.datetime
        ):
            logger.info(f"{source} {last_modified}")

            sha1 = get_sha1(path)

            existing = DataSource.objects.filter(url__contains=".gov.uk", sha1=sha1)
            if existing:
                # hash matches that hash of some BODS data
                logger.info(f"  skipping, {sha1=} matches {existing=}")
            else:
                command.region_id = source.region_id
                command.service_ids = set()
                command.route_ids = set()

                # for "end date is in the past" warnings
                command.source.datetime = timezone.now()

                with log_time_taken(logger):
                    handle_file(command, path)

                    command.mark_old_services_as_not_current()

                    clean_up(source, [command.source])

                    command.finish_services()

            command.source.sha1 = sha1
            command.source.datetime = last_modified
            command.source.save()

            logger.info(
                f"  {command.source.route_set.order_by('end_date').distinct('end_date').values('end_date')}"
            )
            logger.info(f"  {get_operator_ids(command.source)}")
        else:
            need_to_sleep = True


def do_stagecoach_source(command, last_modified, filename, nocs):
    logger.info(f"{command.source.url} {last_modified}")

    # avoid importing old data
    command.source.datetime = timezone.now()

    with log_time_taken(logger):
        handle_file(command, filename)

        command.mark_old_services_as_not_current()

    command.source.datetime = last_modified
    command.source.save()

    logger.info(
        f"  {command.source.route_set.order_by('end_date').distinct('end_date').values('end_date')}"
    )
    operators = get_operator_ids(command.source)
    logger.info(f"  {operators=}")
    unexpected = [o for o in operators if o not in nocs]
    if unexpected:
        logger.info(f"  {unexpected=} (not in {nocs})")


def stagecoach(specific_operator=None):
    command = get_command()

    session = requests.Session()

    timetable_data_sources = TimetableDataSource.objects.filter(
        url__startswith="https://opendata.stagecoachbus.com", active=True
    )
    if specific_operator:
        timetable_data_sources = timetable_data_sources.filter(
            operators=specific_operator
        )
        if not timetable_data_sources:
            logger.info(f"no timetable data sources for noc {specific_operator}")
            return
        logger.info(timetable_data_sources)

    for source in timetable_data_sources:
        command.region_id = source.region_id
        command.service_ids = set()
        command.route_ids = set()
        command.garages = {}

        nocs = list(source.operators.values_list("noc", flat=True))

        filename = Path(source.url).name
        path = settings.DATA_DIR / filename

        command.source, _ = DataSource.objects.get_or_create(
            {"name": source.name}, url=source.url
        )

        modified, last_modified = download_if_modified(path, command.source, session)
        sha1 = get_sha1(path)

        if command.source.datetime != last_modified:
            modified = True

        if modified:
            # use sha1 checksum to check if file has really changed -
            # last_modified seems to change every night
            # even when contents stay the same
            if sha1 == command.source.sha1 or not command.source.older_than(
                last_modified
            ):
                modified = False

            command.source.sha1 = sha1

            if modified or specific_operator:
                do_stagecoach_source(command, last_modified, filename, nocs)

        clean_up(source, [command.source])
        command.finish_services()


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("api_key", type=str)
        parser.add_argument("operator", type=str, nargs="?")

    def handle(self, api_key, operator, **options):
        if api_key == "stagecoach":
            stagecoach(operator)
        elif api_key == "ticketer":
            ticketer(operator)
        else:
            bus_open_data(api_key, operator)
