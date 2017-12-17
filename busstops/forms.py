from django import forms
from haystack.forms import SearchForm
from haystack.query import SQ, AutoQuery


class ContactForm(forms.Form):
    name = forms.CharField(label='Name')
    email = forms.EmailField(label='Email address')
    message = forms.CharField(label='Message', widget=forms.Textarea)
    referrer = forms.CharField(label='Referrer', required=False,
                               widget=forms.HiddenInput)


class CustomSearchForm(SearchForm):
    """https://django-haystack.readthedocs.io/en/master/boost.html#field-boost"""
    def search(self):
        if not self.is_valid():
            return self.no_query_found()

        if not self.cleaned_data.get('q'):
            return self.no_query_found()

        q = self.cleaned_data['q']
        sqs = self.searchqueryset.filter(SQ(name=AutoQuery(q)) | SQ(text=AutoQuery(q)))

        if self.load_all:
            sqs = sqs.load_all()

        return sqs.highlight()
