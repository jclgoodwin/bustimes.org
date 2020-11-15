from django.views.generic.detail import DetailView
from .models import Tariff


class TariffDetailView(DetailView):
    model = Tariff
    queryset = model.objects.prefetch_related(
        'faretable_set__row_set__cell_set__price_group',
        'faretable_set__column_set'
    )
