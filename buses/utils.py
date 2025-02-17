import re
from functools import wraps

from django.contrib.auth.models import AnonymousUser
from django.middleware.cache import FetchFromCacheMiddleware, UpdateCacheMiddleware


def minify(template_source):
    """Alternative to django_template_minifier's minify function"""
    if "<" in template_source and "<pre" not in template_source:
        template_source = re.sub(r"\n+ +", "\n", template_source)
    return template_source


def cache_page(max_age):
    def _cache_controller(view_func):
        fetch_from_cache_middleware = FetchFromCacheMiddleware(view_func)
        update_cache_middleware = UpdateCacheMiddleware(view_func)

        @wraps(view_func)
        def _cache_controlled(request, *args, **kw):
            # anonymise request
            request.user = AnonymousUser

            response = fetch_from_cache_middleware.process_request(request)
            if response:
                return response

            response = view_func(request, *args, **kw)

            update_cache_middleware.cache_timeout = max_age
            update_cache_middleware.process_response(request, response)

            return response

        return _cache_controlled

    return _cache_controller


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
