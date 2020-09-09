from django import forms


class RegistrationForm(forms.Form):
    email_address = forms.EmailField()
