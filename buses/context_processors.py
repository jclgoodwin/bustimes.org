def ad(request):
    path = request.path
    if (
        "/vehicles" in path
        or path.endswith("/debug")
        or path.startswith("/accounts/")
        or path.startswith("/fares/")
        or path.startswith("/sources/")
        or "/tickets" in path
    ):
        return {"ad": False}

    return {"ad": True}
