from datetime import datetime
from requests import Session
from django.contrib.gis.geos import Point
from django.db.models import Q
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from multidb.pinning import use_primary_db
from busstops.models import DataSource, Journey, Service
from .models import Vehicle, VehicleLocation, VehicleJourney
from .management.import_live_vehicles import calculate_bearing


session = Session()


def register_user(source):
    parts = source.url.split()
    response = session.post(parts[0], json={
        "operatingSystem": "iOS",
        "function": "register_user",
        "apiKey": parts[1],
    })
    user_token = response.json()['data']['user_token']
    source.url = f'{parts[0]} {parts[1]} {user_token}'
    source.save()


def handle_item(source, stop, item):
    if not (item['vehicle_number']):
        return

    service_name = item['service_name']

    vehicle = str(item['vehicle_number'])
    if len(vehicle) == 6:
        if vehicle[:2] == '21':
            operator = 'KBUS'
        elif vehicle[:2] == '20':
            operator = 'TBTN'
        elif vehicle[:2] == '30':
            operator = 'NOCT'
        vehicle = int(vehicle[2:])
    else:
        operator = 'NCTR'

    defaults = {
        'source': source,
        'destination': item['journey_destination'],
        'route_name': service_name
    }

    if service_name in {'two', 'mickleover', 'allestree', 'comet', 'harlequin'}:
        service_name = 'the ' + service_name
        operator = 'TBTN'
    elif service_name == 'calverton connection':
        service_name = 'the calverton'
        operator = 'TBTN'
    elif service_name == 'royal derby':
        service_name = 'the royal'
        operator = 'TBTN'
    elif service_name == 'ECO':
        service_name = 'Ecolink'
        operator = 'NOCT'
    elif service_name == 'skylink Derby':
        service_name = 'Skylink Leicester Derby'
        operator = 'KBUS'
    elif service_name == 'skylink express':
        service_name = 'Skylink Clifton'
        operator = 'TBTN'
    elif service_name == 'pronto':
        operator = 'TBTN'
    elif operator == 'NCTR':
        service_name = service_name.split()[-1]

    services = Service.objects.filter(current=True)
    if operator == 'KBUS' or operator == 'TBTN':
        operator_services = services.filter(operator__in=['KBUS', 'TBTN'])
    else:
        operator_services = services.filter(operator=operator)

    querysets = [
        operator_services.filter(Q(line_name__iexact=service_name) | Q(line_brand__iexact=service_name)),
    ]
    if ' ' in service_name:
        querysets.append(operator_services.filter(line_name__iexact=service_name.split()[-1]))

    for queryset in querysets:
        try:
            defaults['service'] = queryset.get()
            break
        except (Service.DoesNotExist, Service.MultipleObjectsReturned):
            continue

    vehicle, _ = Vehicle.objects.update_or_create({
        'source': source,
        'fleet_number': vehicle,
    }, code=vehicle, operator_id=operator)

    if not (vehicle.colours or vehicle.livery_id):
        vehicle.colours = item['vehicle_colour']
        vehicle.save()

    journey, journey_created = VehicleJourney.objects.get_or_create(
        defaults,
        vehicle=vehicle,
        datetime=timezone.make_aware(datetime.fromtimestamp(item['origin_departure_time']))
    )

    if not (item['vehicle_location_lng'] and item['vehicle_location_lat']):
        return

    latlong = Point(item['vehicle_location_lng'], item['vehicle_location_lat'])
    if not journey_created:
        if vehicle.latest_location and vehicle.latest_location.latlong == latlong:
            return

    journey_id = journey.id
    if vehicle.latest_location:
        if journey.datetime > source.datetime:
            journey_id = vehicle.latest_location.journey_id
        elif vehicle.latest_location.latlong == latlong:
            if vehicle.latest_location.journey_id != journey_id:
                vehicle.latest_location.journey_id = journey_id
                vehicle.latest_location.save(update_fields=['journey'])
            return

    with transaction.atomic():
        heading = None
        if vehicle.latest_location:
            if (source.datetime - vehicle.latest_location.datetime).total_seconds() < 1200:
                heading = calculate_bearing(vehicle.latest_location.latlong, latlong)
            vehicle.latest_location.current = False
            vehicle.latest_location.save(update_fields=['current'])
        vehicle.latest_location = VehicleLocation.objects.create(
            journey_id=journey_id,
            latlong=latlong,
            datetime=source.datetime,
            heading=heading,
            current=True
        )
        vehicle.save(update_fields=['latest_location'])
    vehicle.update_last_modified()


def get_stop_departures(source, stop):
    parts = source.url.split()
    if len(parts) < 3:
        register_user(source)
        parts = source.url.split()

    cache_key = f'{parts[0]}:{stop.atco_code}'
    if cache.get(cache_key):
        return
    cache.set(cache_key, True, 69)

    response = session.post(parts[0], json={
        "apiKey": parts[1],
        "function": "get_realtime_full",
        "token": parts[2],
        "atcoCode": stop.atco_code
    }, timeout=2)
    return response.json()['data']


@use_primary_db
def rifkind(service_id):
    source = DataSource.objects.get(name='Rifkind')

    now = timezone.now()
    journeys = Journey.objects.filter(service=service_id, datetime__lt=now, stopusageusage__datetime__gt=now).distinct()
    source.datetime = now
    stops = set()
    for journey in journeys:
        stops.add(journey.stopusageusage_set.last().stop)
    for stop in stops:
        items = get_stop_departures(source, stop)
        if items:
            for item in items:
                handle_item(source, stop, item)
