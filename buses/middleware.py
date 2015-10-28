from django.middleware.common import BrokenLinkEmailsMiddleware


class BrokenLinkEmailsMiddleware(BrokenLinkEmailsMiddleware, object):


    def process_response(self, request, response):
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            request.META['REMOTE_ADDR'] = request.META['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
        return super(BrokenLinkEmailsMiddleware, self).process_response(request, response)
