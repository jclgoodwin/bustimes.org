from django import forms
from django.core.exceptions import ValidationError
from antispam.honeypot.forms import HoneypotField
from antispam import akismet


class ContactForm(forms.Form):
    name = forms.CharField(label='Name')
    email = forms.EmailField(label='Email address')
    message = forms.CharField(label='Message', widget=forms.Textarea)
    spam_honeypot_field = HoneypotField()
    referrer = forms.CharField(label='Referrer', required=False,
                               widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        if self.request and self.is_valid() and 'seen_cookie_message' not in self.request.COOKIES and akismet.check(
            request=akismet.Request.from_django_request(self.request),
            comment=akismet.Comment(
                content=self.cleaned_data['message'],
                type='comment',
                author=akismet.Author(
                    name=self.cleaned_data['name'],
                    email=self.cleaned_data['email']
                )
            )
        ):
            raise ValidationError('Spam detected', code='spam-protection')


class SearchForm(forms.Form):
    q = forms.CharField(widget=forms.TextInput(attrs={"type": "search"}))
