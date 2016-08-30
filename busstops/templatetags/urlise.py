"""https://github.com/jazzband/django-pipeline/issues/295"""

from __future__ import unicode_literals
import codecs

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.html import urlize

register = template.Library()


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlise(value, autoescape=None):
    return mark_safe(
        urlize(value, nofollow=True)
        .replace('">https://', '">')
        .replace('">http://', '">')
        .replace('"http://megabus.com"', '"https://www.awin1.com/cread.php?s=259863&v=2678&q=124178&r=242611"')
        .replace('"http://www.megabus.com"', '"https://www.awin1.com/cread.php?s=259863&v=2678&q=124178&r=242611"')
    )
