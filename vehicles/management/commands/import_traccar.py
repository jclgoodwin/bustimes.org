import requests
from datetime import datetime, timezone

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Exists, OuterRef, Q
from django.db import IntegrityError

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
                item["ticket_machine_code"] = attributes.get("etmID")  # Use custom attribute for ticket machine code
                item["fleet_code"] = attributes.get("fleetNo")
                item["operatorId"] = attributes.get("NOC")
                item["route_name"] = attributes.get("srvNo", "").strip()  # Ensure it's a string
                item["destination"] = attributes.get("dest", "").strip()  # Ensure it's a string
                item["name"] = device_data.get("name")

                # Debugging print to confirm data
                print(f"Device ID: {key}, Ticket Machine Code: {item['ticket_machine_code']}, Route Name: {item['route_name']}, Destination: {item['destination']}")

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
    vehicle_code = str(item["ticket_machine_code"])
    operator_id = item.get("operatorId")

    print(f"Processing vehicle {vehicle_code}, Operator ID: {operator_id}")  # Debugging print

    # Check if operator exists in cache
    operator = self.operators.get(operator_id) if operator_id else None
    if operator is None:
        print(f"Operator {operator_id} not found in the operators cache! Trying to fetch from database.")
        
        # Fetch operator using the noc field instead of operatorcode
        operator = Operator.objects.filter(noc=operator_id).first()
        if operator is None:
            print(f"Operator with noc {operator_id} not found in the database. Skipping vehicle {vehicle_code}.")
            return None, False
        else:
            print(f"Operator {operator_id} fetched from database: {operator}")

    else:
        print(f"Operator found: {operator}")

    # Normalize vehicle code: Assuming vehicle code prefix is 'nctr-' or something like it
    normalized_vehicle_code = f"{operator_id.lower()}-{vehicle_code.split('-')[-1]}"

    # Check if vehicle exists in cache
    if vehicle_code in self.vehicle_cache:
        vehicle = self.vehicle_cache[vehicle_code]
        return vehicle, False

    # Try to fetch the vehicle by matching both operator and vehicle code
    print(f"Querying for vehicle: operator={operator}, vehicle_code={normalized_vehicle_code}")
    vehicle = Vehicle.objects.filter(operator=operator, code__iexact=normalized_vehicle_code).first()

    if vehicle:
        print(f"Found vehicle {vehicle_code} for operator {operator}")
        return vehicle, False

    if item.get("heading") == 0:
        print(f"Heading is 0, skipping vehicle {vehicle_code}")
        return None, False

    # If vehicle doesn't exist, create a new one
    try:
        print(f"Creating vehicle with code {normalized_vehicle_code} and operator {operator}")
        vehicle = Vehicle.objects.create(
            operator=operator,
            source=self.source,
            code=normalized_vehicle_code,
            # Fleet code is not passed here anymore
        )

        # 🚀 Get the journey for this vehicle
        journey = self.get_journey(item, vehicle)

        # 🔗 Link the journey to the vehicle and save
        vehicle.current_journey = journey
        vehicle.save()

        print(f"🚀 Vehicle {vehicle.code} assigned to Journey {journey.route_name} -> {journey.destination}")

        return vehicle, True

    except IntegrityError:
        # Handle the case where a duplicate vehicle exists with the same code and operator
        print(f"Duplicate vehicle {vehicle_code} for operator {operator_id} detected. Fetching existing vehicle.")
        vehicle = Vehicle.objects.get(code=normalized_vehicle_code, operator=operator)
        return vehicle, False

    def get_journey(self, item, vehicle):
        # Extract necessary information from the item
        operator_id = item.get("operatorId", "").strip() if item.get("operatorId") else None
        route_name = item.get("route_name", "").strip()  # Ensure clean route_name
        destination = item.get("destination", "").strip()  # Ensure clean destination
        departure_time = self.get_datetime(item)  # Get the correct departure time

        # Fetch the operator if it's provided
        operator = self.operators.get(operator_id) if operator_id else None

        print(f"Attempting to create/update journey for Route: {route_name}, Operator: {operator_id}, Departure Time: {departure_time}")

        # Check for an existing journey (trip) for this vehicle on the given route and time
        journey = VehicleJourney.objects.filter(
            route_name=route_name,
            vehicle=vehicle,
            datetime__date=departure_time.date(),
            datetime__hour=departure_time.hour
        ).first()

        if journey:
            # Journey found, check if destination has changed
            if journey.destination != destination:
                print(f"Destination changed for {journey.route_name} -> {journey.destination} -> Creating a new journey.")
                
                # Create a new journey if destination has changed
                journey = VehicleJourney(
                    datetime=departure_time,  # Keep the same time
                    destination=destination,  # Updated destination
                    route_name=route_name,
                    source=self.source,
                    vehicle=vehicle,  # Link the vehicle
                    code=item.get("tripId", route_name)
                )
                journey.save()  # Save the new journey
                print(f"Created new journey: Route {journey.route_name}, Destination {journey.destination}")
            else:
                # No destination change, just update the existing journey
                print(f"Found existing journey: {journey.route_name} -> {journey.destination}. No change needed.")
                journey.destination = destination
                journey.save()  # Update the journey

        else:
            # No journey found, create a new one
            print(f"No existing journey found for {route_name}. Creating a new journey.")
            journey = VehicleJourney(
                datetime=departure_time,  # Keep the same time
                destination=destination,
                route_name=route_name,
                source=self.source,
                vehicle=vehicle,  # Link the vehicle
                code=item.get("tripId", route_name)
            )
            journey.save()  # Save the new journey
            print(f"Created new journey: Route {journey.route_name}, Destination {journey.destination}")

        return journey



    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['longitude']} {item['latitude']})"),
            heading=item.get("heading"),
        )
