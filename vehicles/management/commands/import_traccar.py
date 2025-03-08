from datetime import datetime, timezone
from flask import Flask, request, jsonify
import requests

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Exists, OuterRef, Q

from busstops.models import Operator, Service, StopPoint
from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand

app = Flask(__name__)
TRACCAR_URL = "https://demo.traccar.org"
TRACCAR_USER = "your_username"
TRACCAR_PASSWORD = "your_password"

def parse_timestamp(timestamp):
    if timestamp:
        return datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc)

def to_milliseconds(timestamp):
    return int(timestamp * 1000)

def fetch_traccar_data():
    response = requests.get(f"{TRACCAR_URL}/api/positions", auth=(TRACCAR_USER, TRACCAR_PASSWORD))
    if response.status_code == 200:
        data = response.json()
        print("Traccar Data:", data)  # Add this line
        return data
    return []

def transform_traccar_data(data):
    transformed = {
        "fn": data.get("deviceId", "Unknown"),
        "ut": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "oc": "SDVN",
        "sn": "RED",
        "dn": "INBOUND",
        "sd": "XDARED0.I",
        "so": "SCD",
        "sr": "Honiton Road Park & Ride - Exeter, Paris Street",
        "cd": "False",
        "vc": "False",
        "la": str(data.get("latitude", 0)),
        "lo": str(data.get("longitude", 0)),
        "hg": str(data.get("course", "0")),
        "cg": "",
        "dd": "City Centre Paris S",
        "or": "1100DEC10843",
        "on": "Honiton Road P&R",
        "nr": "1100DEC10085",
        "nn": "Sidwell Street",
        "fr": "1100DEC10468",
        "fs": "Paris Street",
        "ao": "",
        "eo": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "an": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "en": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "ax": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "ex": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "af": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "ef": to_milliseconds(data.get("fixTime", datetime.utcnow().timestamp())),
        "ku": "",
        "td": "7127",
        "pr": "1100DEC10843",
        "cs": "",
        "ns": "",
        "jc": "False",
        "rg": "A"
    }
    print("Transformed Data:", transformed)  # Added print statement
    return transformed

@app.route('/traccar', methods=['GET'])
def receive_traccar_data():
    traccar_data = fetch_traccar_data()
    transformed_data = [transform_traccar_data(item) for item in traccar_data]
    for data in transformed_data:
        process_stagecoach_data(data)
    return jsonify({"status": "success", "transformed_data": transformed_data}), 200

class Command(ImportLiveVehiclesCommand):
    source_name = "Traccar"
    previous_locations = {}

    def do_source(self):
        self.operators = Operator.objects.filter(
            Q(parent="Stagecoach") | Q(noc__in=["SCLK", "MEGA"])
        ).in_bulk()
        return super().do_source()

    @staticmethod
    def get_datetime(item):
        return parse_timestamp(item["ut"])

    def prefetch_vehicles(self, vehicle_codes):
        """Fetches vehicles matching the given codes and stores them in a cache."""
        vehicles = self.vehicles.filter(
            operator__in=self.operators, code__in=vehicle_codes
        )
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_items(self):
        print("Entering get_items")  # Add this line
        super_items = super().get_items()
        print("super().get_items() result:", super_items)
        return# Temporarily return an empty list

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['lo']} {item['la']})"),
            heading=item.get("hg"),
        )

def process_stagecoach_data(data):
    cmd = Command()
    cmd.do_source()  # Initialize command
    items = cmd.get_items()
    
    for item in items:
        cmd.create_vehicle_location(item)
    return True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5051, debug=True)
