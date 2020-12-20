from django.views.generic.detail import DetailView
from django.shortcuts import render
from .forms import FaresForm
from .models import DataSet, Tariff


def index(request):
    datasets = DataSet.objects.all()

    return render(request, 'fares/index.html', {
        'datasets': datasets,
    })


class DataSetDetailView(DetailView):
    model = DataSet

    def get_context_data(self, *args, **kwargs):
        context_data = super().get_context_data(*args, **kwargs)
        context_data['breadcrumb'] = self.object.operators.all()

        if self.request.GET:
            form = FaresForm(self.object.tariff_set.all(), self.request.GET)
            if form.is_valid():
                context_data['results'] = form.get_results()
        else:
            form = FaresForm(self.object.tariff_set.all())

        context_data['form'] = form
        return context_data


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
            form = FaresForm([self.object], self.request.GET)
            if form.is_valid():
                context_data['results'] = form.get_results()
        else:
            form = FaresForm([self.object])

        context_data['form'] = form
        return context_data
