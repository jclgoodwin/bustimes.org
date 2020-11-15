import os
import xml.etree.cElementTree as ET
from django.core.management.base import BaseCommand
from ... import models


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_atco_code(stop):
    ref = stop["@ref"]
    assert ref.startswith("atco:")
    return ref[5:]


def get_user_profile(element):
    return models.UserProfile.objects.get_or_create(
        {
            'name': element.findtext('Name'),
            'min_age': element.findtext('MinimumAge'),
            'max_age': element.findtext('MaximumAge'),
        },
        code=element.attrib["id"]
    )


class Command(BaseCommand):
    def handle_file(self, open_file):
        iterator = ET.iterparse(open_file)

        for _, element in iterator:
            if element.tag[:31] == '{http://www.netex.org.uk/netex}':
                element.tag = element.tag[31:]

        user_profiles = {}
        for usage_parameter in element.find("dataObjects/CompositeFrame/frames/FareFrame/usageParameters"):
            user_profile, created = get_user_profile(usage_parameter)
            user_profiles[user_profile.code] = user_profile

        price_groups = {}
        price_group_prices = {}
        price_groups_element = element.find("dataObjects/CompositeFrame/frames/FareFrame/priceGroups")
        if price_groups_element:
            for price_group_element in price_groups_element:
                price_element = price_group_element.find("members/GeographicalIntervalPrice")  # assume only 1 ~
                price_group, created = models.PriceGroup.objects.get_or_create(
                    code=price_group_element.attrib["id"],
                    amount=price_element.findtext("Amount")
                )
                price_groups[price_group.code] = price_group
                price_group_prices[price_element.attrib["id"]] = price_group

        fare_zones = {}
        fare_zones_element = element.find("dataObjects/CompositeFrame/frames/FareFrame/fareZones")
        if fare_zones_element:
            for fare_zone in fare_zones_element:
                fare_zone, created = models.FareZone.objects.get_or_create(
                    code=fare_zone.attrib['id'], name=fare_zone.findtext("Name")
                )
                fare_zones[fare_zone.code] = fare_zone

        tariffs = {}
        distance_matrix_elements = {}
        for tariff_element in element.find("dataObjects/CompositeFrame/frames/FareFrame/tariffs"):
            tariff, created = models.Tariff.objects.get_or_create(
                code=tariff_element.attrib['id'], name=tariff_element.findtext("Name")
            )

            for fare_structure_element in tariff_element.find("fareStructureElements"):
                distance_matrix_element_elements = fare_structure_element.find("distanceMatrixElements")
                if distance_matrix_element_elements:
                    for distance_matrix_element in distance_matrix_element_elements:
                        start_zone = distance_matrix_element.find("StartTariffZoneRef").attrib["ref"]
                        end_zone = distance_matrix_element.find("EndTariffZoneRef").attrib["ref"]
                        price_group = distance_matrix_element.find("priceGroups/PriceGroupRef").attrib['ref']
                        distance_matrix_element, created = models.DistanceMatrixElement.objects.get_or_create(
                            code=distance_matrix_element.attrib["id"],
                            start_zone=fare_zones[start_zone],
                            end_zone=fare_zones[end_zone],
                            price_group=price_groups[price_group],
                            tariff=tariff,
                        )
                        distance_matrix_elements[distance_matrix_element.code] = distance_matrix_element

                user_profile = fare_structure_element.find("GenericParameterAssignment/limitations/UserProfile")
                if user_profile:
                    user_profile, created = get_user_profile(user_profile)
                    user_profiles[user_profile.code] = user_profile

            tariffs[tariff.code] = tariff

        for fare_table_element in element.find("dataObjects/CompositeFrame/frames/FareFrame/fareTables"):
            tariff_ref = fare_table_element.find("usedIn/TariffRef")
            if tariff_ref is None:
                continue
            tariff_ref = tariff_ref.attrib["ref"]
            user_profile_ref = fare_table_element.find("pricesFor/UserProfileRef").attrib["ref"]
            if user_profile_ref not in user_profiles:
                user_profile_ref = f"fxc:{user_profile_ref}"
            table, created = models.FareTable.objects.update_or_create(
                {
                    "tariff": tariffs[tariff_ref],
                    "user_profile": user_profiles[user_profile_ref],
                    "description": fare_table_element.findtext("Description")
                },
                code=fare_table_element.attrib["id"],
                name=fare_table_element.findtext("Name")
            )

            if not created:
                table.column_set.all().delete()
                table.row_set.all().delete()

            columns = {}
            for column in fare_table_element.find('columns'):
                column = models.Column.objects.create(
                    table=table,
                    code=column.attrib['id'],
                    name=column.findtext('Name'),
                    order=column.attrib['order']
                )
                columns[column.code] = column

            rows = {}
            for row in fare_table_element.find('rows'):
                row = models.Row.objects.create(
                    table=table,
                    code=row.attrib['id'],
                    name=row.findtext('Name'),
                    order=row.attrib['order']
                )
                rows[row.code] = row

            for table in fare_table_element.find('includes'):
                for cell_element in table.find('cells'):
                    columnn_ref = cell_element.find('ColumnRef').attrib['ref']
                    row_ref = cell_element.find('RowRef').attrib['ref']
                    distance_matrix_element_price = cell_element.find("DistanceMatrixElementPrice")
                    price_ref = distance_matrix_element_price.find("GeographicalIntervalPriceRef")
                    distance_matrix_element_ref = distance_matrix_element_price.find("DistanceMatrixElementRef")

                    models.Cell.objects.create(
                        column=columns[columnn_ref],
                        row=rows[row_ref],
                        price_group=price_group_prices[price_ref.attrib["ref"]],
                        distance_matrix_element=distance_matrix_elements[distance_matrix_element_ref.attrib["ref"]]
                    )

    def handle(self, **kwargs):
        path = os.path.join(BASE_DIR, 'data')
        for filename in os.listdir(path):
            print(filename)
            with open(os.path.join(path, filename), "rb") as open_file:
                self.handle_file(open_file)
