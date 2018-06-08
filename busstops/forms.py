import requests
from django import forms
from django.db.models import Q
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point, Polygon
from django.core.exceptions import ValidationError
from haystack.forms import SearchForm
from haystack.query import SQ, AutoQuery
from ukpostcodeutils import validation
from antispam.honeypot.forms import HoneypotField
from antispam import akismet
from .models import Locality


session = requests.Session()


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
        if self.request and self.is_valid() and akismet.check(
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


class CustomSearchForm(SearchForm):
    """https://django-haystack.readthedocs.io/en/master/boost.html#field-boost"""
    def get_postcode(self):
        q = self.cleaned_data['q']
        q = ''.join(q.split()).upper()
        if validation.is_valid_postcode(q):
            res = session.get('https://api.postcodes.io/postcodes/' + q, timeout=2)
            if not res.ok:
                return ''
            result = res.json()['result']
            point = Point(result['longitude'], result['latitude'], srid=4326)
            bbox = Polygon.from_bbox((point.x - .05, point.y - .05, point.x + .05, point.y + .05))
            return Locality.objects.filter(
                latlong__within=bbox
            ).filter(
                Q(stoppoint__active=True) | Q(locality__stoppoint__active=True)
            ).distinct().annotate(
                distance=Distance('latlong', point)
            ).order_by('distance').defer('latlong')[:2]

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
