import re
from django import forms
from django.utils.text import normalize_newlines
from django.db.models import CharField
from webcolors import html5_parse_legacy_color


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


def validate_colour(value):
    if value:
        try:
            html5_parse_legacy_color(value)
        except ValueError as e:
            raise forms.ValidationError(str(e))


def validate_colours(value):
    for colour in value.split():
        validate_colour(colour)


def validate_css(value):
    if value.count("(") != value.count(")"):
        raise forms.ValidationError("Must contain equal numbers of ( and )")
    if "{" in value or "}" in value:
        raise forms.ValidationError("Must not contain { or }")


class ColourField(CharField):
    default_validators = [validate_colour]


class ColoursField(CharField):
    default_validators = [validate_colours]


class CSSField(CharField):
    default_validators = [validate_css]
