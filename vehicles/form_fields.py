from re import sub
from django.forms import CharField, Textarea
from django.utils.text import normalize_newlines


class RegField(CharField):
    def to_python(self, value):
        reg = super().to_python(value)
        return reg.upper().replace(" ", "")


class SummaryField(CharField):
    widget = Textarea(attrs={"rows": 6})

    def to_python(self, value):
        if value:
            value = super().to_python(normalize_newlines(value))

            # trim crap from Flickr URLs
            if "/in/photolist-" in value:
                value = sub(r"/in/photolist(-\w+)+", "", value)

        return value
