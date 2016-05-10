from django import forms

class ContactForm(forms.Form):
    name = forms.CharField(label='Name', required=False)
    email = forms.EmailField(label='Email address', required=False)
    message = forms.CharField(label='Message', required=False, widget=forms.Textarea)
    referrer = forms.CharField(label='Referrer', required=False, widget=forms.HiddenInput)
