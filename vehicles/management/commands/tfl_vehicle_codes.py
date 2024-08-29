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

        scheme = "BODS"

        existing_codes = VehicleCode.objects.filter(
            scheme=scheme, code__startswith="TFLO:"
        ).select_related("vehicle")
        existing_codes = {code.code: code for code in existing_codes}

        response = requests.get(url, timeout=10)

        for line in response.text.split("\n")[1:]:
            # print(line)
            line = json.loads(line)
            _, vehicle_id, reg = line
            reg = reg.strip()
            if reg.isdigit():  # tram?
                continue
            code_code = f"TFLO:{vehicle_id}"
            if code := existing_codes.get(code_code):
                other_vehicle = code.vehicle
                if other_vehicle.code == reg:
                    continue
            else:
                existing_codes[code_code] = VehicleCode(code=code_code, scheme=scheme)
            # create or update VehicleCode
            if not (vehicle := get_tfl_vehicle(reg)):
                continue
            existing_codes[code_code].vehicle = vehicle
            existing_codes[code_code].save()
            if other_vehicle and other_vehicle.id != vehicle.id:
                other_vehicle.delete()
