import json
import requests
from django.core.management.base import BaseCommand
from ...models import Vehicle, VehicleCode


def get_tfl_vehicle(reg):
    try:
        return Vehicle.objects.get(code=reg)
    except Vehicle.DoesNotExist:
        try:
            return Vehicle.objects.get(reg=reg)
        except Vehicle.DoesNotExist as e:
            print(reg, e)  # new vehicle
            return Vehicle.objects.create(code=reg, reg=reg, livery_id=262)
        except Vehicle.MultipleObjectsReturned as e:
            print(reg, e)
    except Vehicle.MultipleObjectsReturned as e:
        print(reg, e)


class Command(BaseCommand):
    def handle(self, *args, **options):
        url = "http://countdown.api.tfl.gov.uk/interfaces/ura/instant_V1?ReturnList=VehicleID,RegistrationNumber"

        scheme = "TFLO"

        existing_codes = VehicleCode.objects.filter(scheme=scheme).select_related(
            "vehicle"
        )
        existing_codes = {code.code: code.vehicle for code in existing_codes}

        response = requests.get(url, timeout=10)

        for line in response.text.split()[1:]:
            line = json.loads(line)
            _, vehicle_id, reg = line
            if reg.isdigit():  # tram?
                continue
            vehicle_id = str(vehicle_id)
            if vehicle_id not in existing_codes:
                vehicle = get_tfl_vehicle(reg)
                if not vehicle:
                    continue
                code = VehicleCode.objects.create(
                    code=vehicle_id, scheme=scheme, vehicle=vehicle
                )
                existing_codes[vehicle_id] = code
                Vehicle.objects.filter(code=vehicle_id, operator=None).delete()
