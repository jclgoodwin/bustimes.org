from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(label='Name')
    email = forms.EmailField(label='Email address')
    message = forms.CharField(label='Message', widget=forms.Textarea)
    referrer = forms.CharField(label='Referrer', required=False, widget=forms.HiddenInput)
