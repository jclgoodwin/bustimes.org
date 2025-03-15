from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import urlize
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlise(value, autoescape=None):
    """Like the built-in Django urlize filter,
    but strips the 'https://www.' from the link text,
    and replaces Megabus and National Express URLs with venal affiliate ones
    """

    markup = (
        urlize(value, nofollow=True)
        .replace('">https://', '">', 1)
        .replace('">http://', '">', 1)
        .replace('">www.', '">', 1)
    )
    markup = markup.replace("/</a>", "</a>", 1)
    if "nationalexpress." in markup:
        replacement = '"https://nationalexpress.prf.hn/click/camref:1011ljPYw"'
        markup = markup.replace('"http://www.nationalexpress.com"', replacement, 1)
    return mark_safe(markup)
