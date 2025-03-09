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
        # Initialize vehicle_cache here
        self.vehicle_cache = {}

        # Load operators
        self.operators = Operator.objects.filter(
            Q(parent="midland Group") | Q(noc__in=["MDEM"])
        ).in_bulk(field_name="noc")  # Store operators by their "noc" field

        print(f"Operators loaded: {self.operators.keys()}")  # Debugging print

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
                device_data = traccar_devices.get(key, {})
                attributes = device_data.get("attributes", {})

                # Extract necessary fields
                item["fleet_code"] = attributes.get("fleetNumber")
                item["operatorId"] = attributes.get("operatorId")
                item["route_name"] = attributes.get("serviceNumber", "").strip()  # Ensure it's a string
                item["destination"] = attributes.get("destination", "").strip()  # Ensure it's a string
                item["name"] = device_data.get("name")

                # Debugging print to confirm data
                print(f"Device ID: {key}, Service Number: {item['route_name']}, Destination: {item['destination']}")

                items.append(item)
                vehicle_codes.append(key)
                self.previous_locations[key] = value

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
            for device in devices:
                print(f"Device ID: {device['id']}, Raw Attributes: {device.get('attributes')}")
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
        fleet_code = item.get("fleet_code")
        operator_id = item.get("operatorId")

        print(f"Processing vehicle {vehicle_code}, Operator ID: {operator_id}")  # Debugging print

        if vehicle_code in self.vehicle_cache:
            vehicle = self.vehicle_cache[vehicle_code]

            if fleet_code and vehicle.fleet_code != fleet_code:
                vehicle.fleet_code = fleet_code
                vehicle.save()

            return vehicle, False

        # Ensure `operatorId` is correctly looked up in `self.operators`
        operator = self.operators.get(operator_id) if operator_id else None

        if not operator:
            print(f"Operator {operator_id} not found!")  # Debugging print

        vehicle = Vehicle.objects.filter(operator=None, code__iexact=vehicle_code).first()

        if vehicle or item.get("heading") == 0:
            return vehicle, False

        vehicle = Vehicle.objects.create(
            operator=operator,
            source=self.source,
            code=vehicle_code,
            fleet_code=fleet_code,
        )

        # 🚀 Get the journey for this vehicle
        journey = self.get_journey(item, vehicle)

        # 🔗 Link the journey to the vehicle and save
        vehicle.current_journey = journey
        vehicle.save()

        print(f"🚀 Vehicle {vehicle.code} assigned to Journey {journey.route_name} -> {journey.destination}")

        return vehicle, True

    def get_journey(self, item, vehicle):
        departure_time = self.get_datetime(item)

        route_name = item.get("route_name", item.get("serviceNumber", ""))
        destination = item.get("destination", "")

        # Debugging: Check the route_name and destination before proceeding
        print(f"Debugging Journey: Route: {route_name}, Destination: {destination}")  # This is your debug print

        # Assuming self.operators is a dictionary or list of operators
        operator_id = self.operators[0].id if isinstance(self.operators, list) else list(self.operators.values())[0].id

        # Attempt to get the existing journey by route_name, operator, and code
        # You may need to change 'code' or 'route_name' based on your actual field mapping
        journey = VehicleJourney.objects.filter(
            route_name=route_name,
            operator_id=operator_id,  # Use the resolved operator_id
            code=item.get("tripId", route_name)  # Or route_name if tripId is not available
        ).first()

        if journey:
            # Journey exists, update it
            journey.datetime = departure_time
            journey.destination = destination
            # Update any other fields as needed
            print(f"🚍 Journey updated: Route {journey.route_name}, Destination {journey.destination}")
        else:
            # Journey does not exist, create a new one
            journey = VehicleJourney(
                datetime=departure_time,
                destination=destination,
                route_name=route_name,
                source=self.source,  # Ensure source is assigned
                operator_id=operator_id,  # Make sure operator is correctly set
                code=item.get("tripId", route_name)
            )
            print(f"✅ Journey created: Route {journey.route_name}, Destination {journey.destination}")

        # Save the journey (whether new or updated)
        journey.save()

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['longitude']} {item['latitude']})"),
            heading=item.get("heading"),
        )
