from django.contrib.gis.geos import Polygon
from ciso8601 import parse_datetime
from django.utils.timezone import make_aware


def get_bounding_box(request):
    return Polygon.from_bbox(
        [request.GET[key] for key in ("xmin", "ymin", "xmax", "ymax")]
    )


def get_datetime(string):
    """return a timezone-aware datetime object
    from a string like 2021-07-05T12:01:57
    (the value of a CreationDateTime or ModificationDateTime attribute)
    """

    if string:
        datetime = parse_datetime(string)
        if not datetime.tzinfo:
            return make_aware(datetime)
        return datetime
