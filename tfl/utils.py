from collections import OrderedDict
from datetime import timedelta

from django.utils import timezone

from busstops.models import StopPoint
from bustimes.models import StopTime
from vehicles import rtpi

from .models import Journey, JourneyDriveTime, JourneyWaitTime, StopInPattern


def get_service_date(journey, departure):
    """start_time can be after 24:00, relative to the previous day"""
    return timezone.localdate(departure) - timedelta(days=journey.start_time.days)


def get_stop_times(journey):
    """StopTimes (not saved, some with unsaved StopPoints) relative to the
    service date"""
    base_version_id = journey.base_version_id

    stops_in_pattern = list(
        StopInPattern.objects.filter(
            base_version_id=base_version_id, pattern_idx=journey.pattern_idx
        )
        .select_related("stop__stop_point")
        .order_by("sequence_no")
    )
    if not stops_in_pattern:
        return []

    drive_times = {
        (dt.stop_in_pattern_from_idx, dt.stop_in_pattern_to_idx): dt.drive_time
        for dt in JourneyDriveTime.objects.filter(
            base_version_id=base_version_id, journey_idx=journey.idx
        )
    }
    wait_times = {
        wt.stop_in_pattern_idx: wt.wait_time
        for wt in JourneyWaitTime.objects.filter(
            base_version_id=base_version_id, journey_idx=journey.idx
        )
    }

    stop_times = []
    time = journey.start_time
    previous_idx = None
    for sip in stops_in_pattern:
        if previous_idx is not None:
            time += drive_times.get((previous_idx, sip.idx), timedelta())
        arrival = time
        time += wait_times.get(sip.idx, timedelta())
        tfl_stop = sip.stop
        # not a NaPTAN stop - a stand, garage, etc
        passenger = bool(tfl_stop and tfl_stop.naptan_code)
        stop = tfl_stop and tfl_stop.stop_point
        if not stop:
            stop = StopPoint(
                common_name=tfl_stop.name if tfl_stop else "",
                latlong=tfl_stop.latlong if tfl_stop else None,
            )
        stop_times.append(
            StopTime(
                stop=stop,
                arrival=arrival,
                departure=time,
                sequence=sip.sequence_no,
                timing_point=bool(sip.timing_point_code),
                pick_up=passenger,
                set_down=passenger,
            )
        )
        previous_idx = sip.idx

    return stop_times


class ProgressJourney:
    def __init__(self, date, stop_times, pairs):
        self.date = date
        self.stop_times = stop_times
        self.pairs = pairs


# (code, line_name, departure) -> ProgressJourney or None
CACHE_MAXSIZE = 10_000

_cache: OrderedDict[tuple, ProgressJourney | None] = OrderedDict()


def get_progress_journey(vehicle_journey, service_id=None) -> ProgressJourney | None:
    """for the AVL importer - the service date, and stop times for working out
    progress and delay"""
    departure = vehicle_journey.datetime
    key = (vehicle_journey.code, vehicle_journey.route_name, departure)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]

    entry = None
    if journey := Journey.from_vehicle_journey(vehicle_journey):
        stop_times = [
            st for st in get_stop_times(journey) if st.stop_id and st.stop.latlong
        ]
        route_links = rtpi.get_route_links(service_id, rtpi.pair_keys(stop_times))
        pairs = rtpi.Pairs(stop_times, route_links)
        stop_field = StopTime._meta.get_field("stop")
        for stop_time in stop_times:
            # save a bit of memory
            stop_field.delete_cached_value(stop_time)
        entry = ProgressJourney(get_service_date(journey, departure), stop_times, pairs)

    _cache[key] = entry
    if len(_cache) > CACHE_MAXSIZE:
        _cache.popitem(last=False)
    return entry
