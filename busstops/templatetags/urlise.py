from __future__ import unicode_literals

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.html import urlize

register = template.Library()


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlise(value, autoescape=None):
    """Like the built-in Django urlize filter,
    but strips the 'http://' from the link text,
    and replaces Megabus URLs with venal Affiliate Window ones
    """
    megabus = '"https://www.awin1.com/awclick.php?mid=2678&amp;id=242611&amp;clickref=notes"'
    national_express = '"http://www.awin1.com/awclick.php?mid=2197&amp;id=271445&amp;clickref=j2gkl249fo001sq6005jd&amp;p=http%3A%2F%2Fwww.nationalexpress.com"'  # noqa
    return mark_safe(
        urlize(value, nofollow=True)
        .replace('">https://', '">')
        .replace('">http://', '">')
        .replace('"http://megabus.com"', megabus)
        .replace('"http://uk.megabus.com"', megabus)
        .replace('"http://nationalexpress.com"', national_express)
        .replace('"http://www.nationalexpress.com"', national_express)
    )
