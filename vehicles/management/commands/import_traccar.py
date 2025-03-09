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

        # Check if operator exists in cache
        operator = self.operators.get(operator_id) if operator_id else None
        if operator is None:
            print(f"Operator {operator_id} not found in the operators cache!")
        else:
            print(f"Operator found: {operator}")

        if vehicle_code in self.vehicle_cache:
            vehicle = self.vehicle_cache[vehicle_code]

            if fleet_code and vehicle.fleet_code != fleet_code:
                vehicle.fleet_code = fleet_code
                vehicle.save()

            return vehicle, False

        # Try to fetch or create vehicle here, even if the operator is missing
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
        # Safely handle 'operatorId' to avoid the AttributeError when it's None
        operator_id = item.get("operatorId", "").strip() if item.get("operatorId") else None
        route_name = item.get("route_name", "").strip()  # Clean up the route name
        destination = item.get("destination", "").strip()  # Clean up the destination
        departure_time = self.get_datetime(item)  # Ensure this is the correct time

        print(f"Attempting to create/update journey with route: {route_name}, operator_id: {operator_id}, departure_time: {departure_time}")

        # Proceed with the usual journey retrieval or creation
        if operator_id:  # Only proceed if we have a valid operator_id
            operator = self.operators.get(operator_id)
        else:
            operator = None

        # Update the filtering to use `operator` instead of `operator_id`
        journey = VehicleJourney.objects.filter(
            route_name=route_name,
            vehicle__operator=operator if operator else None,  # Correctly referencing the operator through the Vehicle model
            code=item.get("tripId", route_name)
        ).first()

        if journey:
            # Existing journey found, update destination, but don't change the time
            print(f"Found existing journey: {journey.route_name} -> {journey.destination}")
            journey.destination = destination
            journey.save()
        else:
            # No existing journey, create a new one
            if not operator_id:  # If operator_id is missing, log and return None
                print(f"Error: Operator ID is missing, cannot create a new journey.")
                return None  # Prevent creation if operator_id is invalid

            # Create a new journey
            journey = VehicleJourney(
                datetime=departure_time,  # Keep the same time
                destination=destination,
                route_name=route_name,
                source=self.source,
                operator=operator,  # Assign operator here
                code=item.get("tripId", route_name)
            )
            print(f"Creating new journey: Route {journey.route_name}, Destination {journey.destination}")
            journey.save()

        return journey


    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['longitude']} {item['latitude']})"),
            heading=item.get("heading"),
        )
