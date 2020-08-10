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
    and replaces Megabus and National Express URLs with venal affiliate ones
    """

    markup = urlize(value, nofollow=True).replace('">https://', '">', 1).replace('">http://', '">', 1)
    markup = markup.replace('/</a>', '</a>', 1)
    if 'megabus' in markup:
        megabus = 'https%3A%2F%2Fuk.megabus.com'
        megabus = f'"https://www.awin1.com/awclick.php?mid=2678&amp;id=242611&amp;clickref=urlise&amp;p={megabus}"'
        markup = markup.replace('"http://megabus.com"', megabus, 1)
        markup = markup.replace('"https://uk.megabus.com"', megabus, 1)
    elif 'nationalexpress' in markup:
        replacement = 'https://clkuk.pvnsolutions.com/brand/contactsnetwork/click?p=230590&amp;a=3022528&amp;g=21039402'
        replacement = f'"{replacement}"'
        markup = markup.replace('"http://nationalexpress.com"', replacement, 1)
        markup = markup.replace('"http://www.nationalexpress.com"', replacement, 1)
        markup = markup.replace('"https://www.nationalexpress.com"', replacement, 1)
    return mark_safe(markup)
