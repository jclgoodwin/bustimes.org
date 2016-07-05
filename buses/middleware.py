"""Special middleware
"""
from django.middleware import common


class BrokenLinkEmailsMiddleware(common.BrokenLinkEmailsMiddleware, object):
    """Like the built-in Django BrokenLinkEmailsMiddleware, but with a more informative IP address
    """
    def process_response(self, request, response):
        """If an X-Forwarded-For header is provided, use it to set the request's REMOTE_ADDR
        """
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            request.META['REMOTE_ADDR'] = request.META['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
        return super(BrokenLinkEmailsMiddleware, self).process_response(request, response)
