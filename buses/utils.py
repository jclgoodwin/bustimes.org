import re
from functools import wraps

from django.contrib.auth.models import AnonymousUser
from django.conf import settings


def minify(template_source):
    """Alternative to django_template_minifier's minify function"""
    if "<" in template_source and "<pre" not in template_source:
        template_source = re.sub(r"\n+ +", "\n", template_source)
    return template_source


def cdn_cache_control(max_age):
    def _cache_controller(view_func):
        @wraps(view_func)
        def _cache_controlled(request, *args, **kw):
            # anonymise request
            request.user = AnonymousUser

            response = view_func(request, *args, **kw)
            response["CDN-Cache-Control"] = (
                f"public, max-age={max_age}, stale-if-error={max_age}"
            )
            return response

        return _cache_controlled

    return _cache_controller


def show_toolbar(request):
    print(request.META, settings.INTERNAL_IPS)
    if request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS:
        return True
    if request.META.get("HTTP_DO_CONNECTING_IP") in settings.INTERNAL_IPS:
        return True
