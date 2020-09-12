from datetime import timedelta
from requests import Session
from django.core.cache import cache
from busstops.models import DataSource
from bustimes.models import get_calendars, Trip
from .management.commands import import_sirivm
from .models import SIRISource


session = Session()


class Poorly(Exception):
    pass


schemes = ('Cornwall SIRI', 'Devon SIRI', 'Bristol SIRI',
           'Leicestershire SIRI', 'Hampshire SIRI', 'West Sussex SIRI')


def siri_one_shot(code, now, locations):
    source = 'Icarus'
    siri_source = SIRISource.objects.get(name=code.scheme[:-5])
    line_name_cache_key = f'{siri_source.url}:{siri_source.requestor_ref}:{code.code}'
    service_cache_key = f'{code.service_id}:{source}'
    if cache.get(line_name_cache_key):
        return 'cached (line name)'
    cached = cache.get(service_cache_key)
    if cached:
        return f'cached ({cached})'
    if siri_source.get_poorly():
        raise Poorly()
    if not locations:
        time_since_midnight = timedelta(hours=now.hour, minutes=now.minute, seconds=now.second,
                                        microseconds=now.microsecond)
        trips = Trip.objects.filter(calendar__in=get_calendars(now), route__service=code.service_id,
                                    start__lte=time_since_midnight + timedelta(minutes=10),
                                    end__gte=time_since_midnight - timedelta(minutes=10))
        if not trips.exists():
            # no journeys currently scheduled, and no vehicles online recently
            cache.set(service_cache_key, 'nothing scheduled', 300)  # back off for 5 minutes
            return 'nothing scheduled'
    cache.set(line_name_cache_key, 'line name', 40)  # cache for 40 seconds
    data = f"""<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
<ServiceRequest><RequestorRef>{siri_source.requestor_ref}</RequestorRef>
<VehicleMonitoringRequest version="1.3"><LineRef>{code.code}</LineRef></VehicleMonitoringRequest>
</ServiceRequest></Siri>"""
    url = siri_source.url.replace('StopM', 'VehicleM', 1)
    response = session.post(url, data=data, timeout=5)
    if 'Client.AUTHENTICATION_FAILED' in response.text:
        cache.set(siri_source.get_poorly_key(), True, 3600)  # back off for an hour
        raise Poorly()
    command = import_sirivm.Command()
    command.source = DataSource.objects.get(name='Icarus')
    for item in import_sirivm.items_from_response(response):
        command.handle_item(item, now, code)
