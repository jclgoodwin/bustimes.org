from django.template import Library

register = Library()


@register.filter
def date_range(date_range=None, lower=None, upper=None):
    if not (date_range or lower or upper):
        return ""
    if date_range:
        lower = date_range.lower
        upper = date_range.upper
    to_format = "%A %-d %B %Y"
    if upper:
        to = upper.strftime(to_format)
        if lower:
            if lower.year == upper.year:
                if lower.month == upper.month:
                    from_format = "%A %-d"
                    lower = lower
                    if lower.day == upper.day:
                        return to
                else:
                    from_format = "%A %-d %B"
            else:
                from_format = to_format
            return f"{lower.strftime(from_format)}\u2009\u2013\u2009{to}"
        return f"Until {to}"
    if lower:
        return f"From {lower.strftime(to_format)}"
