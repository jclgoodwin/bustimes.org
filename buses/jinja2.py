from django.template.defaultfilters import linebreaks, linebreaksbr
from django.templatetags.static import static
from django.urls import reverse
from django.utils.safestring import mark_safe
from jinja2 import Environment

from busstops.templatetags.urlise import urlise
from vehicles.context_processors import _liveries_css_version


def environment(**options):
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            "liveries_css_version": _liveries_css_version,
            "urlise": urlise,
            "linebreaksbr": mark_safe(linebreaksbr),
            "linebreaks": mark_safe(linebreaks),
        }
    )
    return env
