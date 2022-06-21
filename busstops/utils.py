from ciso8601 import parse_datetime
from django.contrib.gis.geos import Polygon
from django.utils.timezone import make_aware


def get_bounding_box(request):
    return Polygon.from_bbox(
        [request.GET[key] for key in ("xmin", "ymin", "xmax", "ymax")]
    )


def parse_nptg_datetime(datetime):
    datetime = parse_datetime(datetime)
    if not datetime.tzinfo:
        return make_aware(datetime)
    return datetime
