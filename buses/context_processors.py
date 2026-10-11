def ad(request):
    path = request.path
    if (
        request.user.is_authenticated
        or "/edit" in path
        or path.endswith("/debug")
        or path.startswith(("/accounts/", "/fares/", "/sources/"))
        or "/tickets" in path
    ):
        return {"ad": False}

    return {"ad": True}
