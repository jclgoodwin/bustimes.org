from django.middleware.gzip import GZipMiddleware
from django.utils.cache import add_never_cache_headers
from multidb.pinning import pin_this_thread, unpin_this_thread
from whitenoise.middleware import WhiteNoiseMiddleware


class WhiteNoiseWithFallbackMiddleware(WhiteNoiseMiddleware):
    # https://github.com/evansd/whitenoise/issues/245
    def __call__(self, request):
        response = super().__call__(request)
        if response.status_code == 404 and request.path.startswith(self.static_prefix):
            fallback_path = self.get_name_without_hash(request.path)
            request.path = request.path_info = fallback_path
            fallback_response = super().__call__(request)
            if fallback_response:
                response = fallback_response
            add_never_cache_headers(response)
        return response


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


class GZipIfNotStreamingMiddleware(GZipMiddleware):
    def process_response(self, request, response):
        if response.streaming:
            return response

        return super().process_response(request, response)
