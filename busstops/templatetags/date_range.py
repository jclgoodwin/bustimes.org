from django import template


register = template.Library()


@register.filter
def date_range(date_range):
    if not date_range:
        return ''
    to_format = '%-d %B %Y'
    if date_range.lower and date_range.upper:
        if date_range.lower.year == date_range.upper.year:
            if date_range.lower.month == date_range.upper.month:
                from_format = '%-d'
            else:
                from_format = '%-d %B'
        else:
            from_format = to_format
        return f'{date_range.lower.strftime(from_format)}–{date_range.upper.strftime(to_format)}'
    if date_range.lower:
        return f'From {date_range.lower.strftime(to_format)}'
    if date_range.upper:
        return f'Until {date_range.upper.strftime(to_format)}'
