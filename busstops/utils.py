from django.contrib.gis.geos import Polygon


def get_bounding_box(request):
    return Polygon.from_bbox(
        [request.GET[key] for key in ("xmin", "ymin", "xmax", "ymax")]
    )
