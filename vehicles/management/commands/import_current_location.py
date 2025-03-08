from datetime import datetime, timezone
from flask import Flask, request, jsonify
import requests

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Exists, OuterRef, Q

from busstops.models import Operator, Service, StopPoint
from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand

app = Flask(__name__)

def parse_timestamp(timestamp):
    if timestamp:
        return datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc)

def to_milliseconds(timestamp):
    return int(timestamp * 1000)

def transform_traccar_data(data):
    return {
        "fn": data.get("device", "Unknown"),
        "ut": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "oc": "SDVN",
        "sn": "RED",
        "dn": "INBOUND",
        "sd": "XDARED0.I",
        "so": "SCD",
        "sr": "Honiton Road Park & Ride - Exeter, Paris Street",
        "cd": "False",
        "vc": "False",
        "la": str(data.get("lat", 0)),
        "lo": str(data.get("lon", 0)),
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
        "eo": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "an": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "en": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "ax": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "ex": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "af": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "ef": to_milliseconds(data.get("timestamp", datetime.utcnow().timestamp())),
        "ku": "",
        "td": "7127",
        "pr": "1100DEC10843",
        "cs": "",
        "ns": "",
        "jc": "False",
        "rg": "A"
    }

@app.route('/traccar', methods=['POST'])
def receive_traccar_data():
    data = request.json
    transformed_data = transform_traccar_data(data)
    process_stagecoach_data(transformed_data)
    return jsonify({"status": "success", "transformed_data": transformed_data}), 200

class Command(ImportLiveVehiclesCommand):
    source_name = "midland"
    previous_locations = {}

    def do_source(self):
        self.operators = Operator.objects.filter(
            Q(parent="Stagecoach") | Q(noc__in=["SCLK", "MEGA"])
        ).in_bulk()
        return super().do_source()

    @staticmethod
    def get_datetime(item):
        return parse_timestamp(item["ut"])

    def get_items(self):
        items = []
        vehicle_codes = []
        for item in super().get_items()["services"]:
            key = item["fn"]
            value = (item["ut"],)
            if self.previous_locations.get(key) != value:
                items.append(item)
                vehicle_codes.append(key)
                self.previous_locations[key] = value
        self.prefetch_vehicles(vehicle_codes)
        return items

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['lo']} {item['la']})"),
            heading=item.get("hg"),
        )

def process_stagecoach_data(data):
    cmd = Command()
    cmd.handle()  # Runs the ImportLiveVehiclesCommand
    return True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5055, debug=True)
