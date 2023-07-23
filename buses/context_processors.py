def ad(request):
    if (
        request.path.endswith("/edit")
        or request.path.startswith("/accounts/")
        or request.path.startswith("/fares/")
    ):
        return {"ad": False}

    if request.headers.get("cf-connecting-ip", "").startswith("138.38.229."):
        return {"ad": not request.path.startswith("/stops/")}

    return {"ad": True}
