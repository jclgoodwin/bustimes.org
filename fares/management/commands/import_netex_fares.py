import os
import xmltodict
from django.core.management.base import BaseCommand
from ... import models


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_atco_code(stop):
    ref = stop["@ref"]
    assert ref.startswith("atco:")
    return ref[5:]


def handle_user_profile(data):
    user_profile, created = models.UserProfile.objects.get_or_create(
        {
            'name': data['Name'],
            'min_age': data.get('MinimumAge'),
            'max_age': data.get('MaximumAge'),
        },
        code=data["@id"]
    )
    return user_profile


def handle_price_group(data):
    group, created = models.PriceGroup.objects.get_or_create(
        code=data["@id"], amount=data["members"]["GeographicalIntervalPrice"]["Amount"]
    )
    return group


def handle_zone(data):
    zone, created = models.FareZone.objects.update_or_create(
        {"code": data["@id"]}, name=data["Name"]
    )
    stops = data["members"]["ScheduledStopPointRef"]
    zone.stops.set([get_atco_code(stop) for stop in stops])
    return zone


def handle_tariff(data, fare_zones, price_groups):
    tariff, created = models.Tariff.objects.get_or_create(
        code=data["@id"], name=data["Name"]
    )

    for fare_structure_element in data["fareStructureElements"]["FareStructureElement"]:
        if "distanceMatrixElements" in fare_structure_element:
            for data in fare_structure_element["distanceMatrixElements"][
                "DistanceMatrixElement"
            ]:

                (
                    distance_matrix_element,
                    created,
                ) = models.DistanceMatrixElement.objects.get_or_create(
                    code=data["@id"],
                    start_zone=fare_zones[data["StartTariffZoneRef"]["@ref"]],
                    end_zone=fare_zones[data["EndTariffZoneRef"]["@ref"]],
                    price_group=price_groups[
                        data["priceGroups"]["PriceGroupRef"]["@ref"]
                    ],
                    tariff=tariff,
                )
    return tariff


def handle_fare_table(data, tariffs, user_profiles):
    user_profile_ref = data["pricesFor"]["UserProfileRef"]["@ref"]
    table, created = models.FareTable.objects.update_or_create(
        {
            "tariff": tariffs[data["usedIn"]["TariffRef"]["@ref"]],
            "user_profile": user_profiles[f'fxc:{user_profile_ref}'],
        },
        code=data["@id"],
        name=data["Name"]
    )


def handle_file(open_file):
    data = xmltodict.parse(
        open_file,
        dict_constructor=dict,
        force_list=["ScheduledStopPointRef", "PriceGroup", "FareTable", "Tariff"],
    )
    composite_frames = data["PublicationDelivery"]["dataObjects"]["CompositeFrame"]

    user_profiles = {}
    fare_zones = {}
    price_groups = {}
    tariffs = {}

    for composite_frame in composite_frames:
        if composite_frame["@responsibilitySetRef"] == "fxc:FXC_metadata":
            frame = composite_frame["frames"]["FareFrame"]
            if "usageParameters" in frame:
                for profile in frame["usageParameters"]["UserProfile"]:
                    profile = handle_user_profile(profile)
                    user_profiles[profile.code] = profile

    for composite_frame in composite_frames:
        if composite_frame["@responsibilitySetRef"] == "tariffs":

            # print(composite_frame['Name'])
            # print(composite_frame['Description'])
            # print(composite_frame['ValidBetween'])
            # print(composite_frame['frames']['ResourceFrame'])
            # print(composite_frame['frames']['SiteFrame'])

            for frame in composite_frame["frames"]["FareFrame"]:
                if "priceGroups" in frame:
                    for group in frame["priceGroups"]["PriceGroup"]:
                        group = handle_price_group(group)
                        price_groups[group.code] = group

                if "fareZones" in frame:
                    for zone in frame["fareZones"]["FareZone"]:
                        zone = handle_zone(zone)
                        fare_zones[zone.code] = zone

            for frame in composite_frame["frames"]["FareFrame"]:
                if "tariffs" in frame:
                    for tariff in frame["tariffs"]["Tariff"]:
                        tariff = handle_tariff(tariff, fare_zones, price_groups)
                        tariffs[tariff.code] = tariff

                if "fareTables" in frame:
                    for table in frame["fareTables"]["FareTable"]:
                        handle_fare_table(table, tariffs, user_profiles)


class Command(BaseCommand):
    def handle(self, **kwargs):
        paths = [
            "connexions_Harrogate_Coa_16.286Z_IOpbaMX.xml",
            "LYNX 39 single.xml",
            "LYNX Coast.xml",
            "LYNX Townrider.xml",
        ]

        for path in paths:
            path = os.path.join(BASE_DIR, path)

            with open(path, "rb") as open_file:
                handle_file(open_file)
