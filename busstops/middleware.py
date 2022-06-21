from multidb.pinning import pin_this_thread, unpin_this_thread


def pin_db_middleware(get_response):
    def middleware(request):
        if (
            request.method == "POST"
            or request.path.startswith("/admin/")
            or request.path.startswith("/accounts/")
            or "/edit" in request.path
        ):
            pin_this_thread()
        else:
            unpin_this_thread()
        return get_response(request)

    return middleware
