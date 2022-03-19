import requests

import json
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe
from django.views.generic.detail import DetailView

from busstops.models import Operator, DataSource, OperatorCode, Service

from .forms import FaresForm
from .models import DataSet, Tariff


def index(request):
    datasets = DataSet.objects.order_by('-datetime')

    return render(request, 'fares_index.html', {
        'datasets': datasets,
    })


class Tickets:
    def __init__(self, operator):
        self.operator = operator

    def __str__(self):
        return "Tickets"

    def get_absolute_url(self):
        return f"{self.operator.get_absolute_url()}/tickets"


def operator_tickets(request, slug):
    operator = get_object_or_404(Operator, slug=slug)
    source = get_object_or_404(DataSource, name="MyTrip")
    code = get_object_or_404(OperatorCode, operator=operator, source=source)

    response = requests.get(f"{source.url}/{code.code}", headers={
        "x-api-key": source.settings["x-api-key"]
    }).json()

    categories = response["_links"]["topup:category"]
    groupings = response["_embedded"]["render"]["group_by"]
    for grouping in groupings:
        grouping["categories"] = [category for category in categories if category["type"] == grouping["value"]]

    context = {
        "breadcrumb": [operator],
        "operator": operator,
        "groupings": groupings
    }

    return render(request, 'operator_tickets.html', context)


def operator_ticket(request, slug, id):
    operator = get_object_or_404(Operator, slug=slug)
    source = get_object_or_404(DataSource, name="MyTrip")

    response = requests.get(f"{source.url}/{id}", headers={
        "x-api-key": source.settings["x-api-key"]
    }).json()

    context = {
        "breadcrumb": [operator, Tickets(operator)],
        "operator": operator,
        "title": response["title"],
        "description": response["description"],
        "categories": response["_embedded"]["topup"],
    }
    for category in context["categories"]:
        category["price"] = f"{category['price'] / 100:.2f}"

    json_ld = json.dumps([{
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": category['title'],
        "description": category['description'],
        "offers": {
            "@type": "Offer",
            "url": f"https://mytrip.today/app/view-product/{category['id']}",
            "priceCurrency": "GBP",
            "price": category["price"]
        }
    } for category in context["categories"]])
    context["json_ld"] = mark_safe(f'<script type="application/ld+json">{json_ld}</script>')

    return render(request, 'operator_ticket.html', context)


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
        'faretable_set__row_set__cell_set__price',
        'faretable_set__column_set',
        'faretable_set__user_profile',
        'faretable_set__sales_offer_package',
        'price_set__time_interval',
        'price_set__sales_offer_package',
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


def service_fares(request, slug):
    service = get_object_or_404(Service, slug=slug)
    tariffs = Tariff.objects.filter(services=service)

    if not tariffs:
        raise Http404

    return render(request, 'service_fares.html', {
        'breadcrumb': [service],
        'tariffs': tariffs,
    })
