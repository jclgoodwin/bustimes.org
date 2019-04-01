from django.views.generic.detail import DetailView
from django.http import Http404
from django.db.models import Max
from busstops.models import Operator
from .models import Licence, Registration


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

        if not (context['registrations'] or context['cancelled']):
            raise Http404()

        operator = Operator.objects.filter(operatorcode__code=self.object.licence_number,
                                           operatorcode__source__name='Licence')
        context['operator'] = operator.select_related('region').first()
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

        operator = Operator.objects.filter(operatorcode__code=self.object.licence.licence_number,
                                           operatorcode__source__name='Licence')
        context['operator'] = operator.select_related('region').first()
        context['breadcrumb'] = [self.object.licence]

        if context['operator']:
            context['breadcrumb'] = [
                context['operator'].region,
                context['operator'],
            ] + context['breadcrumb']

        return context
