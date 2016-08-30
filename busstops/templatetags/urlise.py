"""https://github.com/jazzband/django-pipeline/issues/295"""

from __future__ import unicode_literals

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
        .replace('"http://megabus.com"', '"https://www.awin1.com/awclick.php?mid=2678&amp;id=242611"')
        .replace('"http://www.megabus.com"', '"https://www.awin1.com/awclick.php?mid=2678&amp;id=242611"')
    )
