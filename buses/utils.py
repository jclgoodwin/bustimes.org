import re
from django.conf import settings


def minify(template_source):
    """Alternative to django_template_minifier's minify function"""
    if "<" in template_source and "<pre" not in template_source:
        template_source = re.sub(r"\n+ +", "\n", template_source)
    return template_source


def show_toolbar(request):
    if request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS:
        return True
    if request.META.get("HTTP_DO_CONNECTING_IP") in settings.INTERNAL_IPS:
        return True
