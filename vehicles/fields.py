from django import forms


class RegField(forms.CharField):
    def to_python(self, value):
        reg = super().to_python(value)
        return reg.upper().replace(' ', '')
