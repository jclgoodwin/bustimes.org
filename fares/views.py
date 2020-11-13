from django.views.generic.detail import DetailView
from .models import Tariff


class TariffDetailView(DetailView):
    model = Tariff
