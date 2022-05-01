from vcr import use_cassette
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from .models import Livery, Vehicle


class VehicleCodeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Livery.objects.create(id=262, name="red", published=True)
        Vehicle.objects.create(reg="LTZ1454")
        Vehicle.objects.create(reg="LTZ1454", code="LK67EOM")
        Vehicle.objects.create(code="LK67EOM")
        Vehicle.objects.create(reg="LK17CZP")
        Vehicle.objects.create(code="BV10WWO")
        Vehicle.objects.create(code="7642")

    def test_import_tfl(self):
        path = settings.BASE_DIR / "fixtures" / "vcr" / "tfl_vehicle_code.yaml"
        with use_cassette(str(path)):
            call_command("tfl_vehicle_codes")

        self.assertEqual(Vehicle.objects.all().count(), 6)
