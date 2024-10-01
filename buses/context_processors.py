def ad(request):
    path = request.path
    if (
        "/edit" in path
        or path.endswith("/debug")
        or path.startswith("/accounts/")
        or path.startswith("/fares/")
        or path.startswith("/sources/")
        or "/tickets" in path
    ):
        return {"ad": False}

    if request.headers.get("cf-connecting-ip", "").startswith("138.38.229."):
        return {"ad": not path.startswith("/stops/")}

    return {"ad": True}
