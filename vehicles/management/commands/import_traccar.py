import requests
from datetime import datetime, timezone

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Exists, OuterRef, Q

from busstops.models import Operator, Service, StopPoint
from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


# Traccar API login information
TRACCAR_API_URL = "https://your-traccar-api-url.com/api"
TRACCAR_USER = "your_username" # To avoid conflicts, use your email you signed up with
TRACCAR_PASSWORD = "your_password"
TRACCAR_API_KEY = "your_api_key"  # For authentication if needed, adjust according to Traccar's API

# Sample data mappings (adjust based on the Traccar API response format)
# Traccar returns data in JSON format, such as:
# {
#     "id": 1,
#     "deviceId": 12345,
#     "name": "Vehicle XYZ",
#     "latitude": 50.7314606,
#     "longitude": -3.7003877,
#     "speed": 45.0,
#     "heading": 66,
#     "timestamp": 1599550016135
# }

def parse_timestamp(timestamp):
    """ Parse ISO 8601 timestamp string into a timezone-aware datetime """
    if timestamp:
        return datetime.fromisoformat(timestamp).astimezone(timezone.utc)

def has_stop(stop):
    return Exists(
        StopPoint.objects.filter(service=OuterRef("pk"), locality__stoppoint=stop)
    )


class Command(ImportLiveVehiclesCommand):

    source_name = "Traccar"
    previous_locations = {}

    def do_source(self):
        self.operators = Operator.objects.filter(
            Q(parent="midland Group") | Q(noc__in=["MDEM"])
        ).in_bulk()
        return super().do_source()

    @staticmethod
    def get_datetime(item):
        """ Get datetime from Traccar data item """
        # Check multiple possible fields for timestamp: 'timestamp', 'deviceTime', 'fixTime'
        # Default to 'deviceTime' if available
        timestamp = item.get("timestamp") or item.get("deviceTime") or item.get("fixTime")
        return parse_timestamp(timestamp)

    def prefetch_vehicles(self, vehicle_codes):
        vehicles = self.vehicles.filter(
            operator__in=self.operators, code__in=vehicle_codes
        )
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_items(self):
        items = []
        vehicle_codes = []

        # Fetch data from Traccar API
        traccar_positions = self.fetch_traccar_data()  # /positions
        traccar_devices = self.fetch_traccar_devices()  # /devices

        for item in traccar_positions:
            key = str(item["deviceId"])
            value = (self.get_datetime(item),)

            if self.previous_locations.get(key) != value:
                # Merge position data with device attributes
                device_data = traccar_devices.get(key, {})
                item["fleet_code"] = device_data.get("attributes", {}).get("fleetNumber", "")  # Provide default fallback
                item["name"] = device_data.get("name")  # Optional: Store device name

                items.append(item)
                vehicle_codes.append(key)
                self.previous_locations[key] = value

        self.prefetch_vehicles(vehicle_codes)
        return items


    def fetch_traccar_devices(self):
        """ Fetch additional vehicle details from Traccar API's /devices endpoint """
        response = requests.get(
            f"{TRACCAR_API_URL}/devices",
            auth=(TRACCAR_USER, TRACCAR_PASSWORD),
            headers={"Authorization": f"Bearer {TRACCAR_API_KEY}"},
        )

        if response.status_code == 200:
            devices = response.json()
            return {str(device["id"]): device for device in devices}  # Map by deviceId
        else:
            print(f"Error fetching devices from Traccar: {response.status_code}")
            return {}

    def fetch_traccar_data(self):
        """ Fetch the live vehicle data from Traccar API """
        response = requests.get(
            f"{TRACCAR_API_URL}/positions",
            auth=(TRACCAR_USER, TRACCAR_PASSWORD),
            headers={"Authorization": f"Bearer {TRACCAR_API_KEY}"},
        )

        if response.status_code == 200:
            return response.json()  # Assuming JSON response
        else:
            print(f"Error fetching data from Traccar: {response.status_code}")
            return []

    def get_vehicle(self, item) -> tuple[Vehicle, bool]:
        vehicle_code = str(item["deviceId"])
        fleet_code = item.get("fleet_code", "")  # Provide default fallback for fleet_code
        operator_id = item.get("operatorId")

        if vehicle_code in self.vehicle_cache:
            vehicle = self.vehicle_cache[vehicle_code]

            # Update fleet_code if missing
            if fleet_code and vehicle.fleet_code != fleet_code:
                vehicle.fleet_code = fleet_code
                vehicle.save()

            return vehicle, False

        if operator_id in self.operators:
            operator = self.operators[operator_id]
        else:
            operator = None

        vehicle = Vehicle.objects.filter(operator=None, code__iexact=vehicle_code).first()

        if vehicle or item.get("heading") == 0:
            return vehicle, False

        vehicle = Vehicle.objects.create(
            operator=operator,
            source=self.source,
            code=vehicle_code,
            fleet_code=fleet_code or "",  # Ensure fleet_code is not None
        )

        return vehicle, True


    def get_journey(self, item, vehicle):
        departure_time = self.get_datetime(item)  # Use get_datetime for consistency

        journey = VehicleJourney(
            datetime=departure_time,
            destination=item.get("destination", ""),
            route_name=item.get("serviceNumber", ""),
        )

        if code := item.get("tripId", ""):
            journey.code = code

        if not journey.service_id and journey.route_name:
            services = Service.objects.filter(current=True, operator__in=self.operators)
            stop = item.get("originStopReference")

            if stop:
                services = services.filter(has_stop(stop))

            if item.get("finalStopReference"):
                services = services.filter(has_stop(item["finalStopReference"]))

            journey.service = services.filter(
                Q(route__line_name__iexact=journey.route_name)
                | Q(line_name__iexact=journey.route_name)
            ).first()

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['longitude']} {item['latitude']})"),
            heading=item.get("heading"),
        )
