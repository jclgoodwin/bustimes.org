from datetime import datetime

from django.contrib.syndication.views import Feed
from django.db.models import Exists, Max, OuterRef
from django.views.generic.detail import DetailView

from busstops.models import Service
from busstops.views import get_colours
from bustimes.models import Route

from .models import Licence, Registration, Variation


class UpperCaseSlugMixin:
    def get_object(self):
        self.kwargs["slug"] = self.kwargs["slug"].upper()
        return super().get_object()


class LicenceView(UpperCaseSlugMixin, DetailView):
    model = Licence
    slug_field = "licence_number"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        registrations = self.object.registration_set.annotate(
            effective_date=Max("variation__effective_date"),
            received_date=Max("variation__date_received"),
        ).order_by("-effective_date", "-received_date")

        context["registrations"] = registrations.filter(registered=True)
        context["cancelled"] = registrations.filter(registered=False)

        operators = self.object.get_operators()
        if operators:
            context["operators"] = operators
            context["breadcrumb"] = [operators[0].region, operators[0]]

        return context


class RegistrationView(UpperCaseSlugMixin, DetailView):
    model = Registration
    slug_field = "registration_number"
    queryset = model.objects.select_related("licence")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["variations"] = self.object.variation_set.all()

        context["breadcrumb"] = [self.object.licence]

        operators = self.object.licence.get_operators()
        if operators:
            context["breadcrumb"] = [
                operators[0].region,
                operators[0],
            ] + context["breadcrumb"]

        services = Service.objects.with_line_names().filter(
            Exists(
                Route.objects.filter(service=OuterRef("id"), registration=self.object)
            ),
            current=True,
        )
        context["services"] = sorted(services, key=Service.get_order)
        if context["services"]:
            context["colours"] = get_colours(context["services"])

        return context


class LicenceFeed(Feed):
    description_template = "rss_description.html"

    def get_object(self, request, licence_number):
        return Licence.objects.get(licence_number=licence_number)

    def title(self, obj):
        return f"{obj} – {obj.name}"

    def link(self, obj):
        return obj.get_absolute_url()

    def items(self, obj):
        items = Variation.objects.filter(registration__licence=obj).exclude(
            date_received=None
        )
        return items.select_related("registration").order_by("-date_received")[:100]

    def item_pubdate(self, item):
        date = item.date_received
        return datetime(date.year, date.month, date.day)


class AreaFeed(Feed):
    pass
