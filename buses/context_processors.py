from django.conf import settings


def ad(request):
    if request.path == "/cookies":
        return {"ad": True}
    if (
        not request.user.is_anonymous
        or request.path.startswith("/vehicles/")
        or request.path.startswith("/accounts/")
        or request.path.startswith("/fares/")
    ):
        return {"ad": False}
    return {"ad": settings.ADS}
