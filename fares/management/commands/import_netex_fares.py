import io
import logging
import xml.etree.cElementTree as ET
import requests
import zipfile
from ciso8601 import parse_datetime
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.utils.http import http_date, parse_http_date
from busstops.models import StopPoint, Operator, Service
from ... import models


logger = logging.getLogger(__name__)


def get_user_profile(element):
    return models.UserProfile.objects.get_or_create(
        {
            "name": element.findtext("Name"),
            "min_age": element.findtext("MinimumAge"),
            "max_age": element.findtext("MaximumAge"),
        },
        code=element.attrib["id"],
    )


def get_sales_offer_package(element):
    return models.SalesOfferPackage.objects.get_or_create(
        code=element.attrib["id"],
        name=element.findtext("Name", ""),
        description=element.findtext("Description", ""),
    )


class Command(BaseCommand):
    base_url = "https://data.bus-data.dft.gov.uk"

    def handle_file(self, source, open_file, filename=None):
        iterator = ET.iterparse(open_file)

        if not filename:
            filename = open_file.name

        try:
            for _, element in iterator:
                # remove NeTEx namespace for simplicity's sake:
                if element.tag[:31] == "{http://www.netex.org.uk/netex}":
                    element.tag = element.tag[31:]
        except ET.ParseError:
            return

        operators = element.findall(
            "dataObjects/CompositeFrame/frames/ResourceFrame/organisations/Operator"
        )
        operators = {operator.attrib["id"]: operator for operator in operators}

        lines = element.findall(
            "dataObjects/CompositeFrame/frames/ServiceFrame/lines/Line"
        )
        lines = {line.attrib["id"]: line for line in lines}
        # print(operators, lines)

        user_profiles = {**self.user_profiles}
        for usage_parameter in element.findall(
            "dataObjects/CompositeFrame/frames/FareFrame/usageParameters/UserProfile"
        ):
            user_profile, created = get_user_profile(usage_parameter)
            user_profiles[user_profile.code] = user_profile

        sales_offer_packages = {**self.sales_offer_packages}
        for sales_offer_package in element.findall(
            "dataObjects/CompositeFrame/frames/FareFrame/salesOfferPackages/SalesOfferPackage"
        ):
            sales_offer_package, created = get_sales_offer_package(sales_offer_package)
            sales_offer_packages[sales_offer_package.code] = sales_offer_package

        price_groups = {}
        price_group_prices = {}
        for price_group_element in element.findall(
            "dataObjects/CompositeFrame/frames/FareFrame/priceGroups/PriceGroup"
        ):
            price_element = price_group_element.find(
                "members/GeographicalIntervalPrice"
            )  # assume only 1 ~
            price = models.Price(amount=price_element.findtext("Amount"))
            price_groups[price_group_element.attrib["id"]] = price
            price_group_prices[price_element.attrib["id"]] = price
        models.Price.objects.bulk_create(price_groups.values())

        fare_zones = {}
        for fare_zone_element in element.findall(
            "dataObjects/CompositeFrame/frames/FareFrame/fareZones/FareZone"
        ):
            fare_zone, created = models.FareZone.objects.get_or_create(
                code=fare_zone_element.attrib["id"],
                name=fare_zone_element.findtext("Name"),
            )
            fare_zones[fare_zone.code] = fare_zone
            # stop_refs = [stop.attrib['ref'] for stop in fare_zone_element.findall('members/ScheduledStopPointRef')]
            # if stop_refs:
            #     try:
            #         if stop_refs[0].startswith('atco'):
            #             fare_zone.stops.set(StopPoint.objects.filter(
            #                 atco_code__in=[stop_ref.removeprefix('atco:') for stop_ref in stop_refs]
            #             ))
            #         # elif stop_refs[0].startswith('naptStop'):
            #         #     fare_zone.stops.set(StopPoint.objects.filter(
            #         #         naptan_code__iexact__in=[stop_ref.removeprefix('naptStop:') for stop_ref in stop_refs]
            #         #     ))
            #         else:
            #             print(stop_refs[0])
            #     except IntegrityError as e:
            #         print(e)

        prices = {}

        tariffs = {}
        time_intervals = {}
        for tariff_element in element.findall(
            "dataObjects/CompositeFrame/frames/FareFrame/tariffs/Tariff"
        ):
            tariff_code = tariff_element.attrib["id"]

            fare_structure_elements = tariff_element.find("fareStructureElements")

            user_profile = None
            trip_type = ""
            if fare_structure_elements:
                user_profile = fare_structure_elements.find(
                    "FareStructureElement/GenericParameterAssignment/limitations/UserProfile"
                )
                if user_profile is not None:
                    user_profile, created = get_user_profile(user_profile)
                    user_profiles[user_profile.code] = user_profile

                trip_type = fare_structure_elements.findtext(
                    "FareStructureElement/GenericParameterAssignment/limitations/RoundTrip/TripType",
                    "",
                )

            type_of_tariff = tariff_element.find("TypeOfTariffRef")
            if type_of_tariff is not None:
                type_of_tariff = type_of_tariff.attrib["ref"].removeprefix("fxc:")

            tariff = models.Tariff.objects.create(
                code=tariff_code,
                name=tariff_element.findtext("Name"),
                source=source,
                filename=filename,
                trip_type=trip_type,
                user_profile=user_profile,
                type_of_tariff=type_of_tariff or "",
            )
            tariffs[tariff.code] = tariff

            operator = tariff_element.find("OperatorRef")
            if operator is not None:
                try:
                    operator = Operator.objects.get(
                        id=operator.attrib["ref"].removeprefix("noc:")
                    )
                except Operator.DoesNotExist:
                    pass
            if operator:
                tariff.operators.add(operator)

                line_ref = tariff_element.find("LineRef")
                if line_ref is not None:
                    line = lines[line_ref.attrib["ref"]]
                    line_name = line.findtext("PublicCode")
                    try:
                        service = Service.objects.get(
                            operator=operator, line_name__iexact=line_name, current=True
                        )
                    except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                        logger.warning(f"{e} {operator} {line_name}")
                    else:
                        tariff.services.add(service)

            distance_matrix_elements = {}
            if fare_structure_elements:
                distance_matrix_element_elements = fare_structure_elements.find(
                    "FareStructureElement/distanceMatrixElements"
                )
                if distance_matrix_element_elements:
                    for distance_matrix_element in distance_matrix_element_elements:

                        price_group_ref = distance_matrix_element.find(
                            "priceGroups/PriceGroupRef"
                        )
                        if price_group_ref is None:
                            continue
                        price_group_ref = price_group_ref.attrib["ref"]

                        start_zone = distance_matrix_element.find(
                            "StartTariffZoneRef"
                        ).attrib["ref"]
                        end_zone = distance_matrix_element.find(
                            "EndTariffZoneRef"
                        ).attrib["ref"]

                        distance_matrix_element = models.DistanceMatrixElement(
                            code=distance_matrix_element.attrib["id"],
                            start_zone=fare_zones[start_zone],
                            end_zone=fare_zones[end_zone],
                            price=price_groups[price_group_ref],
                            tariff=tariff,
                        )
                        distance_matrix_elements[
                            distance_matrix_element.code
                        ] = distance_matrix_element
                models.DistanceMatrixElement.objects.bulk_create(
                    distance_matrix_elements.values()
                )

            if fare_structure_elements:
                access_zones = fare_structure_elements.find(
                    "FareStructureElement/GenericParameterAssignment/validityParameters/FareZoneRef"
                )
                if access_zones is not None:
                    tariff.access_zones.add(fare_zones[access_zones.attrib["ref"]])

            time_intervals_element = tariff_element.find("timeIntervals")
            if time_intervals_element:
                for time_interval in time_intervals_element:
                    time_interval, _ = models.TimeInterval.objects.get_or_create(
                        code=time_interval.attrib["id"],
                        name=time_interval.findtext("Name"),
                        description=time_interval.findtext("Description", ""),
                    )
                    time_intervals[time_interval.code] = time_interval

        for fare_table_element in element.findall(
            "dataObjects/CompositeFrame/frames/FareFrame/fareTables/FareTable"
        ):
            tariff_ref = fare_table_element.find("usedIn/TariffRef")
            if tariff_ref is None:
                pass
            else:
                tariff_ref = tariff_ref.attrib["ref"]
                tariff = tariffs[tariff_ref]

            user_profile_ref = fare_table_element.find("pricesFor/UserProfileRef")
            if user_profile_ref is not None:
                user_profile_ref = user_profile_ref.attrib["ref"]
                if user_profile_ref not in user_profiles:
                    user_profile_ref = f"fxc:{user_profile_ref}"
                user_profile = user_profiles[user_profile_ref]
            else:
                user_profile = None

            sales_offer_package_ref = fare_table_element.find(
                "pricesFor/SalesOfferPackageRef"
            )
            if sales_offer_package_ref is not None:
                sales_offer_package_ref = sales_offer_package_ref.attrib["ref"]
                sales_offer_package = sales_offer_packages[sales_offer_package_ref]
            else:
                sales_offer_package = None

            columns_element = fare_table_element.find("columns")
            rows_element = fare_table_element.find("rows")

            if columns_element and rows_element:
                table, created = models.FareTable.objects.update_or_create(
                    {
                        "user_profile": user_profile,
                        "sales_offer_package": sales_offer_package,
                        "description": fare_table_element.findtext("Description", ""),
                    },
                    tariff=tariff,
                    code=fare_table_element.attrib["id"],
                    name=fare_table_element.findtext("Name", ""),
                )

                if not created:
                    table.column_set.all().delete()
                    table.row_set.all().delete()

                columns = {}
                if columns_element:
                    for column in columns_element:
                        column = models.Column(
                            table=table,
                            code=column.attrib["id"],
                            name=column.findtext("Name"),
                            order=column.attrib.get("order"),
                        )
                        columns[column.code] = column
                models.Column.objects.bulk_create(columns.values())

                rows = {}
                if rows_element:
                    for row in rows_element:
                        row = models.Row(
                            table=table,
                            code=row.attrib["id"],
                            name=row.findtext("Name"),
                            order=row.attrib.get("order"),
                        )
                        rows[row.code] = row
                models.Row.objects.bulk_create(rows.values())

            else:
                table = None

                # Stagecoach
                distance_matrix_elements = tariff_element.find("distanceMatrixElements")
                if distance_matrix_elements:
                    distance_matrix_elements = {
                        element.attrib["id"]: element
                        for element in distance_matrix_elements
                    }

                    for price in fare_table_element.findall(
                        "prices/DistanceMatrixElementPrice"
                    ):
                        distance_matrix_element_ref = price.find(
                            "DistanceMatrixElementRef"
                        ).attrib["ref"]
                        distance_matrix_element = distance_matrix_elements[
                            distance_matrix_element_ref
                        ]
                        amount = price.findtext("Amount")
                        if amount not in prices:
                            prices[amount] = models.Price.objects.create(amount=amount)
                        start_zone = distance_matrix_element.find(
                            "StartTariffZoneRef"
                        ).attrib["ref"]
                        end_zone = distance_matrix_element.find(
                            "EndTariffZoneRef"
                        ).attrib["ref"]
                        models.DistanceMatrixElement.objects.create(
                            tariff=tariff,
                            start_zone=fare_zones[start_zone],
                            end_zone=fare_zones[end_zone],
                            price=prices[amount],
                        )

            cells = []

            for sub_fare_table_element in fare_table_element.findall(
                "includes/FareTable"
            ):
                # fare tables within fare tables
                cells_element = sub_fare_table_element.find("cells")
                if cells_element:
                    for cell_element in cells_element:
                        columnn_ref = cell_element.find("ColumnRef").attrib["ref"]
                        row_ref = cell_element.find("RowRef").attrib["ref"]
                        distance_matrix_element_price = cell_element.find(
                            "DistanceMatrixElementPrice"
                        )
                        if distance_matrix_element_price is None:
                            print(ET.tostring(cell_element).decode())
                            continue
                        price_ref = distance_matrix_element_price.find(
                            "GeographicalIntervalPriceRef"
                        )
                        if price_ref is None:
                            continue
                        distance_matrix_element_ref = (
                            distance_matrix_element_price.find(
                                "DistanceMatrixElementRef"
                            )
                        )

                        if row_ref in rows:
                            row = rows[row_ref]
                        else:
                            # sometimes the RowRef doesn't correspond exactly to a Row id
                            row_ref_suffix = row_ref.split("@")[-1]
                            row_ref_suffix = f"@{row_ref_suffix}"
                            row_refs = [
                                row_ref
                                for row_ref in rows
                                if row_ref.endswith(row_ref_suffix)
                            ]
                            assert len(row_refs) == 1
                            row = rows[row_refs[0]]
                        try:
                            distance_matrix_element_ref = (
                                distance_matrix_element_ref.attrib["ref"]
                            )
                            distance_matrix_element = distance_matrix_elements[
                                distance_matrix_element_ref
                            ]
                        except KeyError as e:
                            print(e)
                            distance_matrix_element = None
                        cells.append(
                            models.Cell(
                                column=columns[columnn_ref],
                                row=row,
                                price=price_group_prices[price_ref.attrib["ref"]],
                                distance_matrix_element=distance_matrix_element,
                            )
                        )

                sales_offer_package_ref = sub_fare_table_element.find(
                    "pricesFor/SalesOfferPackageRef"
                )
                if sales_offer_package_ref is not None:
                    sales_offer_package_ref = sales_offer_package_ref.attrib["ref"]
                    sales_offer_package = sales_offer_packages[sales_offer_package_ref]
                else:
                    sales_offer_package = None

                if sub_fare_table_element.find("includes"):
                    for sub_sub_fare_table_element in sub_fare_table_element.find(
                        "includes"
                    ):
                        cells_element = sub_sub_fare_table_element.find("cells")
                        if cells_element:
                            for cell_element in cells_element:

                                time_interval_price = cell_element.find(
                                    "TimeIntervalPrice"
                                )
                                if time_interval_price:
                                    time_interval = time_interval_price.find(
                                        "TimeIntervalRef"
                                    )
                                    if time_interval is not None:
                                        time_interval = time_intervals[
                                            time_interval.attrib["ref"]
                                        ]
                                    price, created = models.Price.objects.get_or_create(
                                        amount=time_interval_price.findtext("Amount"),
                                        time_interval=time_interval,
                                        tariff=tariff,
                                        sales_offer_package=sales_offer_package,
                                        user_profile=user_profile,
                                    )

            models.Cell.objects.bulk_create(cells)

        # Stagecoach has user profiles and sales offer packages defined separately
        if "_COMMON_" in filename:
            if user_profiles:
                self.user_profiles = user_profiles
            if sales_offer_packages:
                self.sales_offer_packages = sales_offer_packages

    @staticmethod
    def add_arguments(parser):
        parser.add_argument("api_key", type=str)

    def handle_archive(self, dataset, file):
        with zipfile.ZipFile(file) as archive:
            for filename in archive.namelist():
                logger.info(f"  {filename}")
                self.handle_file(dataset, archive.open(filename), filename)

    def handle_bods_dataset(self, item):
        download_url = item["url"]
        dataset_url = download_url.removesuffix("download/")
        modified = parse_datetime(item["modified"])
        try:
            dataset = models.DataSet.objects.get(url=dataset_url)
            if dataset.datetime == modified:
                return dataset
            # has changed
            dataset.tariff_set.all().delete()
        except models.DataSet.DoesNotExist:
            dataset = models.DataSet(
                name=item["name"], description=item["description"], url=dataset_url
            )
            dataset.save()

        logger.info(dataset)

        try:
            dataset.operators.set(item["noc"])
        except IntegrityError:
            logger.warning(item["noc"])

        response = self.session.get(download_url, stream=True)

        self.user_profiles = {}
        self.sales_offer_packages = {}

        if response.headers["Content-Type"] == "text/xml":
            # maybe not fully RFC 6266 compliant
            filename = response.headers["Content-Disposition"].split("filename", 1)[1][
                2:-1
            ]
            logger.info(filename)
            self.handle_file(dataset, response.raw, filename)
        else:
            assert response.headers["Content-Type"] == "application/zip"
            self.handle_archive(dataset, io.BytesIO(response.content))

        dataset.datetime = modified
        dataset.save(update_fields=["datetime"])
        return dataset

    def ticketer(self, noc):
        download_url = f"https://opendata.ticketer.com/uk/{noc}/fares/current.zip"

        dataset, created = models.DataSet.objects.get_or_create(
            {"name": f"{noc}"}, url=download_url
        )

        headers = {}
        if dataset.datetime:
            headers["if-modified-since"] = http_date(dataset.datetime.timestamp())

        response = self.session.get(download_url, headers=headers, stream=True)
        assert response.ok

        if response.status_code == 304:
            return dataset

        last_modified = response.headers["last-modified"]
        last_modified = parse_http_date(last_modified)
        last_modified = datetime.fromtimestamp(last_modified, timezone.utc)

        if dataset.datetime == last_modified:
            return dataset

        logger.info(download_url)

        self.user_profiles = {}
        self.sales_offer_packages = {}

        self.handle_archive(dataset, io.BytesIO(response.content))

        dataset.datetime = last_modified
        dataset.save(update_fields=["datetime"])
        return dataset

    def bod(self, api_key):
        datasets = []
        url = f"{self.base_url}/api/v1/fares/dataset/"
        params = {"api_key": api_key, "status": "published"}
        while url:
            response = self.session.get(url, params=params)
            logger.info(response.url)

            data = response.json()

            for item in data["results"]:
                try:
                    dataset = self.handle_bods_dataset(item)
                    if dataset:
                        datasets.append(dataset.id)
                except (TypeError, IntegrityError) as e:
                    print(e)

            url = data["next"]
            params = None

        # remove removed datasets
        old = models.DataSet.objects.filter(url__startswith=self.base_url).exclude(
            id__in=datasets
        )
        if old:
            logger.info(f"deleting {old}")
            logger.info(f"deleted {old.delete()}")

    def handle(self, api_key, **options):
        self.session = requests.Session()

        if api_key == "ticketer":
            for noc in (
                "FECS",
                "FESX",
                "FCWL",
                "FGLA",
                "FSYO",
                "FWYO",
                "FYOR",
            ):
                self.ticketer(noc)
        else:
            assert len(api_key) == 40
            self.bod(api_key)
