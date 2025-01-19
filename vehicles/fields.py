import re
from django import forms
from django.utils.text import normalize_newlines
from django.db.models import CharField


class RegField(forms.CharField):
    def to_python(self, value):
        reg = super().to_python(value)
        return reg.upper().replace(" ", "")


class SummaryField(forms.CharField):
    widget = forms.Textarea(attrs={"rows": 6})

    def to_python(self, value):
        if value:
            value = super().to_python(normalize_newlines(value))

            # trim crap from Flickr URLs
            if "/in/photolist-" in value:
                value = re.sub(r"/in/photolist(-\w+)+", "", value)

        return value


class ColourField(CharField):
    pass


class ColoursField(CharField):
    pass


class CSSField(CharField):
    pass
