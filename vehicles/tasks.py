from ciso8601 import parse_datetime
from django.db import IntegrityError
from django.db.models import Q
from huey.contrib.djhuey import db_task

from busstops.models import DataSource, Operator

from .models import Vehicle, VehicleJourney


@db_task()
def log_vehicle_journey(service, data, time, destination, source_name, url, trip_id):
    operator_ref = data.get("OperatorRef")
    if operator_ref in ("McG", "SWB", "MID"):
        return

    if not time:
        time = data.get("OriginAimedDepartureTime")
    if not time:
        return

    vehicle = data["VehicleRef"]

    if operator_ref:
        vehicle = vehicle.removeprefix(f"{operator_ref}-")

    vehicle = vehicle.removeprefix("WCM-").removeprefix("SHU-")

    if not vehicle or vehicle == "-":
        return

    operator = None
    if operator_ref:
        operator = Operator.objects.filter(noc=operator_ref).first()

    if not operator:
        try:
            operator = Operator.objects.get(service=service)
        except (Operator.DoesNotExist, Operator.MultipleObjectsReturned):
            return

    if operator.noc == "FABD":  # Aberdeen
        vehicle = vehicle.removeprefix("111-").removeprefix("S-")
    elif operator.parent == "Stagecoach" or operator.noc == "MCGL":
        return

    data_source, _ = DataSource.objects.get_or_create({"url": url}, name=source_name)

    # get or create vehicle
    defaults = {"source": data_source, "operator": operator, "code": vehicle}

    if operator.parent:
        vehicles = Vehicle.objects.filter(operator__parent=operator.parent)
    else:
        vehicles = operator.vehicle_set

    vehicles = vehicles.select_related("latest_journey")

    if vehicle.isdigit():
        defaults["fleet_number"] = vehicle
        vehicles = vehicles.filter(
            Q(code=vehicle)
            | Q(code__endswith=f"-{vehicle}")
            | Q(code__startswith=f"{vehicle}_-_")
        )
    else:
        vehicles = vehicles.filter(code__iexact=vehicle)

    vehicle, created = vehicles.get_or_create(defaults)

    if vehicle.latest_journey and (
        vehicle.latest_journey.datetime == time
        or vehicle.latest_journey.source_id != data_source.id
    ):
        return

    if (
        "FramedVehicleJourneyRef" in data
        and "DatedVehicleJourneyRef" in data["FramedVehicleJourneyRef"]
    ):
        journey_ref = data["FramedVehicleJourneyRef"]["DatedVehicleJourneyRef"]
    else:
        journey_ref = None

    # if journey_ref and journey_ref.startswith("Unknown"):
    #     journey_ref = ""

    time = parse_datetime(time)

    destination = destination or ""
    route_name = data.get("LineName") or data.get("LineRef")

    journeys = vehicle.vehiclejourney_set
    if journeys.filter(datetime=time).exists():
        return
    if (
        journey_ref
        and journeys.filter(
            route_name=route_name, code=journey_ref, datetime__date=time.date()
        ).exists()
    ):
        return

    try:
        journey = VehicleJourney.objects.create(
            vehicle=vehicle,
            service_id=service,
            route_name=route_name,
            code=journey_ref,
            datetime=time,
            source=data_source,
            destination=destination,
            trip_id=trip_id,
        )
    except IntegrityError:
        return

    if not vehicle.latest_journey or vehicle.latest_journey.datetime < journey.datetime:
        vehicle.latest_journey = journey
        vehicle.latest_journey_data = data
        vehicle.save(update_fields=["latest_journey", "latest_journey_data"])
