from django.views.generic.detail import DetailView
from .forms import FaresForm
from .models import DataSet, Tariff


class DataSetDetailView(DetailView):
    model = DataSet


class TariffDetailView(DetailView):
    model = Tariff
    queryset = model.objects.prefetch_related(
        'faretable_set__row_set__cell_set__price_group',
        'faretable_set__column_set',
        'faretable_set__user_profile',
        'faretable_set__sales_offer_package'
    )

    def get_context_data(self, *args, **kwargs):
        context_data = super().get_context_data(*args, **kwargs)
        context_data['breadcrumb'] = [self.object.source]

        if self.request.GET:
            context_data['form'] = FaresForm(self.object, self.request.GET)
        else:
            context_data['form'] = FaresForm(self.object)

        return context_data
