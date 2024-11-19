"""
Based on https://pypi.org/project/time_aware_polyline/
but with no dependencies etc.
"""


def get_coordinate_for_polyline(coordinate):
    """
    Location coordinate to int representation
    """
    return int(round(coordinate * 1e5))


def get_coordinate_from_polyline(int_representation):
    """
    int representation to location coordinate
    """
    return round(int_representation * 1e-5, 5)


def get_gpx_for_polyline(gpx):
    """
    Convert gpx log to int representation
    """
    return (
        get_coordinate_for_polyline(gpx[0]),
        get_coordinate_for_polyline(gpx[1]),
        gpx[2],
    )


def get_gpx_from_decoded(lat_rep, lon_rep, time_stamp_rep):
    """
    Convert int representation to gpx log
    """
    return [
        get_coordinate_from_polyline(lat_rep),
        get_coordinate_from_polyline(lon_rep),
        time_stamp_rep,
    ]


def extend_time_aware_polyline(polyline, gpx_logs, last_gpx_log=None):
    """
    Extend time aware polyline with gpx_logs, given last gpx log
    of the polyline. A gpx log is [lat, lng, time]
    """
    if last_gpx_log:
        last_lat, last_lng, last_time = get_gpx_for_polyline(last_gpx_log)
    else:
        last_lat = last_lng = last_time = 0

    if polyline is None:
        polyline = ""

    if not gpx_logs:
        return polyline

    for gpx_log in gpx_logs:
        lat, lng, time_stamp = get_gpx_for_polyline(gpx_log)
        d_lat = lat - last_lat
        d_lng = lng - last_lng
        d_time = time_stamp - last_time

        # Can be reused for any n-dimensional polyline
        for v in (d_lat, d_lng, d_time):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                polyline += chr((0x20 | (v & 0x1F)) + 63)
                v >>= 5
            polyline += chr(v + 63)

        last_lat, last_lng, last_time = lat, lng, time_stamp

    return polyline


def encode_time_aware_polyline(gpx_logs):
    return extend_time_aware_polyline("", gpx_logs, None)


def get_decoded_dimension_from_polyline(polyline, index):
    """
    Helper method for decoding polylines that returns
    new polyline index and decoded int part of one dimension
    """
    result = 1
    shift = 0

    while True:
        b = ord(polyline[index]) - 63 - 1
        index += 1
        result += b << shift
        shift += 5
        if b < 0x1F:
            break

    return index, (~result >> 1) if (result & 1) != 0 else (result >> 1)


def decode_time_aware_polyline(polyline) -> list:
    """
    Decode time aware polyline into list of gpx logs
    A gpx log is [lat, lng, time]
    """
    gpx_logs = []
    index = lat = lng = time_stamp = 0
    length = len(polyline)

    while index < length:
        index, lat_part = get_decoded_dimension_from_polyline(polyline, index)
        index, lng_part = get_decoded_dimension_from_polyline(polyline, index)
        index, time_part = get_decoded_dimension_from_polyline(polyline, index)
        lat += lat_part
        lng += lng_part
        time_stamp += time_part
        gpx_log = get_gpx_from_decoded(lat, lng, time_stamp)
        gpx_logs.append(gpx_log)

    return gpx_logs
