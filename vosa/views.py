from datetime import datetime
from django.views.generic.detail import DetailView
from django.contrib.syndication.views import Feed
from django.db.models import Max
from .models import Licence, Registration, Variation


class LicenceView(DetailView):
    model = Licence
    slug_field = 'licence_number'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        registrations = self.object.registration_set.annotate(
            effective_date=Max('variation__effective_date'),
            received_date=Max('variation__date_received')
        ).order_by('-effective_date', '-received_date')

        cancelled_statuses = ('Admin Cancelled', 'Cancellation', 'Cancelled', 'Expired', 'Refused', 'Withdrawn')
        context['cancelled'] = registrations.filter(registration_status__in=cancelled_statuses)
        context['registrations'] = registrations.exclude(pk__in=context['cancelled'])

        context['operator'] = self.object.operator_set.select_related('region').first()
        if context['operator']:
            context['breadcrumb'] = [context['operator'].region, context['operator']]

        return context


class RegistrationView(DetailView):
    model = Registration
    slug_field = 'registration_number'
    queryset = model.objects.select_related('licence')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['variations'] = self.object.variation_set.all()

        context['breadcrumb'] = [self.object.licence]

        context['operator'] = self.object.licence.operator_set.select_related('region').first()

        if context['operator']:
            context['breadcrumb'] = [
                context['operator'].region,
                context['operator'],
            ] + context['breadcrumb']

        return context


class LicenceFeed(Feed):
    description_template = 'rss_description.html'

    def get_object(self, request, licence_number):
        return Licence.objects.get(licence_number=licence_number)

    def title(self, obj):
        return f'{obj} – {obj.name}'

    def link(self, obj):
        return obj.get_absolute_url()

    def items(self, obj):
        items = Variation.objects.filter(registration__licence=obj).exclude(date_received=None)
        return items.order_by('-date_received')[:100]

    def item_pubdate(self, item):
        date = item.date_received
        return datetime(date.year, date.month, date.day)


class AreaFeed(Feed):
    pass
