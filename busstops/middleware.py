from multidb.pinning import pin_this_thread, unpin_this_thread


def real_ip_middleware(get_response):
    def middleware(request):
        if 'HTTP_X_REAL_IP' in request.META:
            request.META['REMOTE_ADDR'] = request.META['HTTP_X_REAL_IP']
        return get_response(request)
    return middleware


def pin_db_middleware(get_response):
    def middleware(request):
        if (
            request.method == 'POST'
            or request.path.startswith('/admin/')
            or request.path.startswith('/accounts/')
            or '/edit' in request.path
        ):
            pin_this_thread()
        else:
            unpin_this_thread()
        return get_response(request)

    return middleware
