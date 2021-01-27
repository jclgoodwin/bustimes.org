from django.shortcuts import redirect
from multidb.pinning import pin_this_thread, unpin_this_thread
from .models import Service, StopPoint


def real_ip_middleware(get_response):
    def middleware(request):
        if 'HTTP_X_REAL_IP' in request.META:
            request.META['REMOTE_ADDR'] = request.META['HTTP_X_REAL_IP']
        return get_response(request)
    return middleware


def not_found_redirect_middleware(get_response):
    def middleware(request):
        response = get_response(request)

        if response.status_code == 404 and request.resolver_match:
            if request.resolver_match.url_name == 'service_detail':
                code = request.resolver_match.kwargs['slug']
                services = Service.objects.filter(current=True)

                if code.lower():
                    try:
                        return redirect(services.get(servicecode__scheme='slug', servicecode__code=code))
                    except Service.DoesNotExist:
                        pass
                try:
                    return redirect(services.get(servicecode__scheme='ServiceCode', servicecode__code=code))
                except Service.DoesNotExist:
                    pass

                service_code_parts = code.split('-')
                if len(service_code_parts) >= 4:
                    suggestion = None

                    # e.g. from '17-N4-_-y08-1' to '17-N4-_-y08':
                    suggestion = services.filter(
                        service_code__icontains='_' + '-'.join(service_code_parts[:4]),
                    ).first()

                    # e.g. from '46-holt-circular-1' to '46-holt-circular-2':
                    if not suggestion and code.lower():
                        if service_code_parts[-1].isdigit():
                            slug = '-'.join(service_code_parts[:-1])
                        else:
                            slug = '-'.join(service_code_parts)
                        suggestion = services.filter(slug__startswith=slug).first()

                    if suggestion:
                        return redirect(suggestion)

            elif request.resolver_match.url_name == 'stoppoint_detail':
                try:
                    return redirect(StopPoint.objects.get(naptan_code=request.resolver_match.kwargs['pk']))
                except StopPoint.DoesNotExist:
                    pass

        return response

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
