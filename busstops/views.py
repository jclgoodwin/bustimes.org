"""View definitions."""

import csv
import datetime
import os
import sys
import traceback
from http import HTTPStatus

import requests
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import MultiLineString, Point
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.expressions import ArraySubquery
from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db.models import F, OuterRef, Prefetch, Q, When, Case, Value
from django.db.models.functions import Coalesce, Now
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils import timezone
from django.utils.cache import patch_response_headers
from django.utils.functional import SimpleLazyObject
from django.views.decorators.cache import cache_control
from django.views.generic.detail import DetailView
from redis.exceptions import ConnectionError
from sql_util.utils import Exists, SubqueryMax, SubqueryMin
from ukpostcodeutils import validation

from buses.utils import cdn_cache_control
from bustimes.models import Route, StopTime, Trip
from departures import live
from disruptions.models import Consequence, Situation
from fares.models import FareTable
from vehicles.models import Vehicle
from vehicles.utils import redis_client
from vosa.models import Registration

from . import forms
from .models import (
    AdminArea,
    DataSource,
    District,
    Locality,
    Operator,
    PaymentMethod,
    Region,
    Service,
    ServiceColour,
    StopArea,
    StopPoint,
)
from .utils import get_bounding_box

operator_has_current_services = Exists("service", filter=Q(service__current=True))
operator_has_current_services_or_vehicles = operator_has_current_services | Exists(
    "vehicle", filter=Q(withdrawn=False, latest_journey__isnull=False)
)


def get_colours(services):
    colours = set(service.colour_id for service in services if service.colour_id)
    if colours:
        return ServiceColour.objects.filter(id__in=colours)


def version(request):
    if commit_hash := os.environ.get("COMMIT_HASH"):
        return HttpResponse(
            f"""<a href="https://github.com/jclgoodwin/bustimes.org/commit/{commit_hash}">{commit_hash}</a>""",
        )
    return HttpResponse(
        os.environ.get("KAMAL_CONTAINER_NAME"), content_type="text/plain"
    )


def not_found(request, exception):
    """Custom 404 handler view"""

    context = {}

    if request.resolver_match:
        if request.resolver_match.url_name == "service_detail" and exception.args:
            code = request.resolver_match.kwargs["slug"]
            service_code_parts = code.split("-")

            if len(service_code_parts) >= 4:
                suggestion = None
                services = Service.objects.filter(current=True).only("slug")

                # e.g. from '17-N4-_-y08-1' to '17-N4-_-y08':
                suggestion = services.filter(
                    service_code__icontains="_" + "-".join(service_code_parts[:4]),
                ).first()

                # e.g. from '46-holt-circular-1' to '46-holt-circular-2':
                if not suggestion and code.lower():
                    if service_code_parts[-1].isdigit():
                        slug = "-".join(service_code_parts[:-1])
                    else:
                        slug = "-".join(service_code_parts)
                    suggestion = services.filter(slug__startswith=slug).first()

                if suggestion:
                    return redirect(suggestion)

        elif request.resolver_match.url_name == "stoppoint_detail":
            try:
                return redirect(
                    StopPoint.objects.get(
                        naptan_code__iexact=request.resolver_match.kwargs["pk"]
                    )
                )
            except StopPoint.DoesNotExist:
                pass

        context["exception"] = exception
    elif request.path[:6] == "/STOP/":
        return redirect(f"/stops/{request.path[6:]}")
    elif len(request.path) > 1 and request.path.endswith("/"):
        try:
            resolver_match = resolve(request.path[:-1])
            return resolver_match.func(request, **resolver_match.kwargs)
        except Http404:
            pass

    # assert "#" not in request.path

    # anonymise request (cos response may be cached)
    request.user = AnonymousUser

    if request.resolver_match:
        cache_timeout = 600  # ten minutes
    else:
        cache_timeout = 3600  # no matching url pattern, cache for an hour

    context["ad"] = False
    response = render(request, "404.html", context)
    response.status_code = HTTPStatus.NOT_FOUND
    patch_response_headers(response, cache_timeout=cache_timeout)
    return response


def error(request):
    context = {}
    _, exception, tb = sys.exc_info()
    context["exception"] = exception
    if request.user.is_superuser:
        context["traceback"] = traceback.format_tb(tb)
    response = render(None, "500.html", context)
    response.status_code = 500
    return response


@cache_control(max_age=3600)
def robots_txt(request):
    "robots.txt"

    if request.get_host() == "bustimes.org":  # live site
        content = """User-agent: *
Disallow: /trips/
Disallow: /api/
Disallow: /accounts/
Disallow: /fares/
Disallow: /vehicles/tfl/
Disallow: /services/*/*
Disallow: /sources
Disallow: /*/debug

User-Agent: ImagesiftBot
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: GPTBot
Disallow: /
"""
    else:  # staging site/other
        content = """User-agent: Mediapartners-Google
Disallow:

User-agent: AdsBot-Google
Disallow:

User-agent: *
Disallow: /
"""

    return HttpResponse(content, content_type="text/plain")


def contact(request):
    """Contact page with form"""
    submitted = False
    if request.method == "POST":
        form = forms.ContactForm(request.POST, request=request)
        if form.is_valid():
            subject = form.cleaned_data["message"][:50].splitlines()[0]

            body = [
                form.cleaned_data["message"],
                form.cleaned_data["referrer"],
                request.headers.get("user-agent", ""),
            ]
            if request.user.is_authenticated:
                body.append(f"https://bustimes.org{request.user.get_absolute_url()}")
            body = "\n\n".join(body)

            message = EmailMessage(
                subject,
                body,
                '"{}" <contactform@bustimes.org>'.format(form.cleaned_data["name"]),
                ["contact@bustimes.org"],
                reply_to=[form.cleaned_data["email"]],
            )
            message.send()
            submitted = True
    else:
        referrer = request.headers.get("referer")
        initial = {
            "referrer": referrer,
            "message": request.GET.get("message"),
        }
        if request.user.is_authenticated:
            initial["email"] = request.user.email
        form = forms.ContactForm(initial=initial)
    return render(request, "contact.html", {"form": form, "submitted": submitted})


def status(request):
    context = {
        "sources": DataSource.objects.filter(
            name__in=["National Operator Codes", "NPTG", "NaPTAN", "Irish NaPTAN"]
        ),
        "bod_avl_status": {},
    }

    for key in ("bod_avl_status", "tfw_status"):
        status = cache.get(key, [])
        context["bod_avl_status"][key.split("_")[0]] = [
            {
                "fetched": fetched,
                "timestamp": timestamp,
                "age": fetched - timestamp,
                "items": items,
                "changed": changed,
            }
            for fetched, timestamp, items, changed in status
        ]

    context["statuses"] = cache.get_many(
        [
            "Realtime_Transport_Operators_status",
            "Irish_Citylink_status",
            "Translink_status",
            "Stagecoach_status",
            "Ember_status",
            "TfE_status",
            "jersey_status",
        ]
    ).items()

    return render(
        request,
        "status.html",
        context,
    )


def stats(request):
    return JsonResponse(cache.get("vehicle-tracking-stats", []), safe=False)


def timetable_source_stats(request):
    return JsonResponse(cache.get("timetable-source-stats", []), safe=False)


@cdn_cache_control(3600)
def stops_json(request):
    """JSON endpoint accessed by the JavaScript map,
    listing the active StopPoints within a rectangle,
    in standard GeoJSON format
    """
    try:
        bounding_box = get_bounding_box(request)
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    if bounding_box.area > 0.15:
        return HttpResponseBadRequest()

    results = (
        StopPoint.objects.filter(
            latlong__bboverlaps=bounding_box,
        )
        .annotate(
            line_names=ArrayAgg(
                "service__route__line_name", distinct=True, default=None
            )
        )
        .filter(Exists("service", filter=Q(service__current=True)))
        .select_related("locality")
        .defer("locality__latlong")
    )

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": stop.latlong.coords,
                    },
                    "properties": {
                        "name": stop.get_qualified_name(),
                        "indicator": stop.indicator,
                        "icon": stop.get_icon(),
                        "bearing": stop.get_heading(),
                        "url": stop.get_absolute_url(),
                        "services": stop.get_line_names(),
                        "stop_type": stop.stop_type,
                        "bus_stop_type": stop.bus_stop_type,
                    },
                }
                for stop in results
            ],
        }
    )


class UppercasePrimaryKeyMixin:
    """Normalises the primary key argument to uppercase"""

    def get_object(self, queryset=None):
        """Given a pk argument like 'ea' or 'sndr',
        convert it to 'EA' or 'SNDR',
        then otherwise behaves like ordinary get_object
        """
        primary_key = self.kwargs.get("pk")
        if (
            primary_key is not None
            and "-" not in primary_key
            and not primary_key.isupper()
        ):
            self.kwargs["pk"] = primary_key.upper()
        return super().get_object(queryset)


class RegionDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A single region and the administrative areas in it"""

    model = Region

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["areas"] = self.object.adminarea_set.exclude(name="")
        if len(context["areas"]) == 1:
            context["districts"] = (
                context["areas"][0]
                .district_set.filter(locality__stoppoint__active=True)
                .distinct()
            )
            del context["areas"]

        context["operators"] = Operator.objects.filter(
            operator_has_current_services_or_vehicles,
            Q(region=self.object)
            | Q(
                noc__in=Operator.regions.through.objects.filter(
                    region=self.object
                ).values("operator")
            ),
        ).only("slug", "name")

        if len(context["operators"]) == 1:
            context["services"] = sorted(
                context["operators"][0]
                .service_set.filter(current=True)
                .defer("geometry"),
                key=Service.get_order,
            )

        return context


class AdminAreaDetailView(DetailView):
    """A single administrative area,
    and the districts, localities (or stops) in it
    """

    model = AdminArea
    queryset = model.objects.select_related("region")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        stops = StopPoint.objects.filter(
            Exists("service", filter=Q(service__current=True))
        )

        # Districts in this administrative area
        context["districts"] = self.object.district_set.filter(
            Exists(stops.filter(locality__district=OuterRef("pk")))
        )

        context["operators"] = Operator.objects.filter(
            Exists(
                Service.objects.filter(
                    current=True,
                    operator=OuterRef("pk"),
                    stops__admin_area=self.object,
                )
                .only("id")
                .order_by()
            )
        ).only("slug", "name")

        # Districtless localities in this administrative area
        context["localities"] = self.object.locality_set.filter(
            Exists(stops.filter(locality=OuterRef("pk")))
            | Exists(stops.filter(locality__parent=OuterRef("pk"))),
            district=None,
            parent=None,
        ).defer("latlong")

        if not (context["localities"] or context["districts"]):
            services = Service.objects.filter(current=True).defer(
                "geometry", "search_vector"
            )
            services = services.filter(
                Exists(
                    StopPoint.objects.filter(
                        service=OuterRef("pk"), admin_area=self.object
                    )
                )
            )
            context["services"] = sorted(services, key=Service.get_order)
            context["modes"] = {
                service.mode for service in context["services"] if service.mode
            }
        context["breadcrumb"] = [self.object.region]
        return context

    def render_to_response(self, context):
        if (
            "services" not in context
            and len(context["districts"]) + len(context["localities"]) == 1
        ):
            if not context["localities"]:
                return redirect(context["districts"][0])
            return redirect(context["localities"][0])
        return super().render_to_response(context)


class DistrictDetailView(DetailView):
    """A single district, and the localities in it"""

    model = District
    queryset = model.objects.select_related("admin_area", "admin_area__region")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        stops = StopPoint.objects.filter(active=True)
        context["localities"] = self.object.locality_set.filter(
            Exists(stops.filter(locality=OuterRef("pk")))
            | Exists(stops.filter(locality__parent=OuterRef("pk"))),
        ).defer("latlong")

        context["breadcrumb"] = [self.object.admin_area.region, self.object.admin_area]

        return context

    def render_to_response(self, context):
        if len(context["localities"]) == 1:
            return redirect(context["localities"][0])
        return super().render_to_response(context)


class LocalityDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A single locality, its children (if any), and the stops in it"""

    model = Locality
    queryset = model.objects.select_related(
        "admin_area", "admin_area__region", "district", "parent"
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        stops = StopPoint.objects.filter(active=True)

        has_stops = Exists(stops.filter(locality=OuterRef("pk")))
        has_stops |= Exists(stops.filter(locality__parent=OuterRef("pk")))

        context["localities"] = self.object.locality_set.filter(has_stops).defer(
            "latlong"
        )

        context["adjacent"] = Locality.objects.filter(
            has_stops, adjacent=self.object
        ).defer("latlong")

        context["stops"] = (
            self.object.stoppoint_set.filter(
                has_stop_times,
                service__current=True,
            )
            .annotate(line_names=stop_line_names)
            .order_by("common_name", "indicator")
            .defer("latlong")
        )

        if not (context["localities"] or context["stops"]):
            raise Http404(
                f"Sorry, it looks like no services currently stop at {self.object}"
            )

        if context["stops"]:
            stops = [stop.pk for stop in context["stops"]]
            context["services"] = sorted(
                Service.objects.filter(
                    Exists(
                        StopTime.objects.filter(
                            trip__route=OuterRef("route"),
                            stop__in=stops,
                        )
                        .only("id")
                        .order_by()
                    ),
                    stops__in=stops,
                    current=True,
                )
                .annotate(
                    operators=ArrayAgg("operator__name", distinct=True, default=None),
                    line_names=ArrayAgg(
                        Coalesce("route__line_name", "line_name"),
                        distinct=True,
                        default=None,
                    ),
                )
                .defer("geometry", "search_vector"),
                key=Service.get_order,
            )
            context["modes"] = {
                service.mode for service in context["services"] if service.mode
            }
            context["colours"] = get_colours(context["services"])
        context["breadcrumb"] = [
            crumb
            for crumb in [
                self.object.admin_area.region,
                self.object.admin_area,
                self.object.district,
                self.object.parent,
            ]
            if crumb is not None
        ]

        return context


def get_departures_context(stop, services, form_data) -> dict:
    context = {}
    when = None
    form = forms.DeparturesForm(form_data)
    if form.is_valid():
        date = form.cleaned_data["date"]
        time = form.cleaned_data["time"]
        if time is None:
            time = datetime.time()  # 00:00
        when = datetime.datetime.combine(date, time)
    context["when"] = when
    departures = live.get_departures(stop, services, when)
    context.update(departures)

    if context["departures"]:
        context["has_live"] = any(item.get("live") for item in context["departures"])
        context["has_scheduled"] = any(
            item.get("time") for item in context["departures"]
        )
    if context["when"]:
        if len(context["departures"]) < 12:
            context["next_page"] = {
                "date": context["when"].date() + datetime.timedelta(days=1),
                "time": None,
            }
        elif last_time := context["departures"][-1].get("time"):
            context["next_page"] = {
                "date": last_time.date(),
                "time": last_time.time().strftime("%H:%M"),
            }

    return context


has_stop_times = ~Exists(
    Route.objects.filter(
        ~Q(line_name__iexact=OuterRef("service__line_name")),
        service=OuterRef("service"),
    )
    .only("id")
    .order_by()
) | Exists(
    StopTime.objects.filter(
        trip__route=OuterRef("service__route"),
        stop=OuterRef("pk"),
    )
    .only("id")
    .order_by()
)
stop_line_names = ArrayAgg("service__route__line_name", distinct=True, default=None)


class StopPointDetailView(DetailView):
    """A stop, other stops in the same area, and the services servicing it"""

    model = StopPoint
    queryset = model.objects.select_related(
        "admin_area",
        "admin_area__region",
        "locality",
        "locality__parent",
        "locality__district",
        "stop_area",
    )
    queryset = queryset.defer("locality__latlong", "locality__parent__latlong")

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return get_object_or_404(queryset, pk__iexact=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        services = (
            self.object.service_set.filter(
                Q(route__trip=None) | Q(route__trip__stoptime__stop=self.object),
                current=True,
            )
            .annotate(
                line_names=ArrayAgg(
                    Coalesce("route__line_name", "line_name"),
                    distinct=True,
                    default=None,
                )
            )
            .defer("geometry", "search_vector")
        )
        services = services.annotate(
            operators=ArrayAgg("operator__name", distinct=True, default=None)
        )
        context["services"] = sorted(services, key=Service.get_order)

        context["breadcrumb"] = [
            self.object.get_region(),
            self.object.admin_area,
            self.object.locality and self.object.locality.district,
            self.object.locality and self.object.locality.parent,
            self.object.locality,
        ]

        if not (self.object.active or context["services"]):
            return context

        context.update(get_departures_context(self.object, services, self.request.GET))

        text = ", ".join(
            part
            for part in (
                "on " + self.object.street if self.object.street else None,
                "near " + self.object.crossing if self.object.crossing else None,
                "near " + self.object.landmark if self.object.landmark else None,
            )
            if part is not None
        )
        if text:
            context["text"] = f"{text[0].upper()}{text[1:]}"

        context["modes"] = {
            service.mode for service in context["services"] if service.mode
        }
        context["colours"] = get_colours(context["services"])

        nearby = (
            StopPoint.objects.filter(active=True)
            .order_by("common_name", "indicator")
            .filter(service__current=True)
        )

        if self.object.stop_area_id is not None:
            nearby = nearby.filter(stop_area=self.object.stop_area_id)
        elif self.object.locality or self.object.admin_area:
            nearby = nearby.filter(common_name=self.object.common_name)
            if self.object.locality:
                nearby = nearby.filter(locality=self.object.locality)
            else:
                nearby = nearby.filter(admin_area=self.object.admin_area)
                if self.object.town:
                    nearby = nearby.filter(town=self.object.town)
        else:
            nearby = None

        if nearby is not None:
            context["nearby"] = (
                nearby.exclude(pk=self.object.pk)
                .filter(has_stop_times, service__current=True)
                .annotate(line_names=stop_line_names)
                .defer("latlong")
            )

            if (
                self.object.stop_area
                and self.object.stop_area.name
                and self.object.stop_area.stop_area_type != "GPBS"
            ):
                # stop area (if it is not an on-street pair)
                context["breadcrumb"].append(self.object.stop_area)

        consequences = Consequence.objects.filter(stops=self.object)
        context["situations"] = (
            Situation.objects.filter(
                publication_window__contains=Now(),
                consequence__stops=self.object,
                current=True,
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "consequence_set", queryset=consequences, to_attr="consequences"
                ),
                "link_set",
                "validityperiod_set",
            )
        )

        return context

    def render_to_response(self, context):
        response = super().render_to_response(context)
        if not (self.object.active or context["services"]):
            response.status_code = HTTPStatus.NOT_FOUND
            patch_response_headers(response)
        return response


class StopAreaDetailView(DetailView):
    model = StopArea
    queryset = model.objects.select_related(
        "admin_area",
        "admin_area__region",
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        stops = (
            self.object.stoppoint_set.annotate(
                line_names=ArrayAgg(
                    "service__route__line_name", distinct=True, default=None
                )
            )
            .filter(service__current=True)
            .order_by("common_name", "indicator")
        )
        context["children"] = stops

        services = Service.objects.filter(
            current=True, stops__stop_area=self.object
        ).annotate(operators=ArrayAgg("operator__name", distinct=True, default=None))
        context.update(get_departures_context(self.object, services, self.request.GET))

        context["breadcrumb"] = [
            self.object.admin_area.region,
            self.object.admin_area,
            self.object.parent,
        ]

        if stops:
            for stop in stops:
                if " " in stop.indicator:
                    context["indicator_prefix"] = stop.indicator.split(" ")[
                        0
                    ].title()  # Stand, Stance, Stop
                    break
            if stop.locality:
                context["breadcrumb"] += [stop.locality.parent, stop.locality]

            stops_dict = {stop.pk: stop for stop in stops}

            for item in context["departures"]:
                item["stop_time"].stop = stops_dict[item["stop_time"].stop_id]

        return context


def stop_departures(request, atco_code):
    stop = get_object_or_404(StopPoint, atco_code=atco_code)

    services = stop.service_set.annotate(
        operators=ArrayAgg("operator__name", distinct=True, default=None)
    )

    context = get_departures_context(stop, services, request.GET)

    context["object"] = stop

    return render(request, "departures.html", context)


class OperatorDetailView(DetailView):
    "An operator and the services it operates"

    model = Operator
    queryset = model.objects.select_related("region").prefetch_related("licences")

    def get_object(self, **kwargs):
        try:
            return super().get_object(**kwargs)
        except Http404:
            if "slug" in self.kwargs:
                try:
                    return get_object_or_404(
                        self.queryset,
                        operatorcode__code=self.kwargs["slug"],
                        operatorcode__source__name="slug",
                    )
                except Http404:
                    self.kwargs["pk"] = self.kwargs["slug"].upper()
                    return super().get_object(**kwargs)
            raise

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # services list:

        services = (
            self.object.service_set.with_line_names()
            .filter(current=True)
            .defer("geometry", "search_vector")
        )
        services = services.annotate(start_date=SubqueryMin("route__start_date"))

        if self.object.name == "National Express":
            services = services.annotate(
                group=Case(
                    When(
                        route__code__contains="_Events-",
                        then=Value("Festival & event travel"),
                    ),
                    default=Value(""),
                )
            )

        context["services"] = sorted(services, key=Service.get_order)

        if context["services"]:
            # for 'from {date}' for future services:
            context["today"] = timezone.localdate()

            context["colours"] = get_colours(context["services"])

        context["breadcrumb"] = [self.object.region]

        # this is a bit of a faff,
        # just to avoid doing separate queries
        # for National Operator Codes and MyTrip
        operator_codes = self.object.operatorcode_set.annotate(
            source_name=F("source__name")
        )

        # tickets tab:
        if any(code.source_name == "MyTrip" for code in operator_codes):
            context["tickets_link"] = reverse(
                "operator_tickets", kwargs={"slug": self.object.slug}
            )
        elif self.object.name == "National Express":
            context["tickets_link"] = (
                "https://nationalexpress.prf.hn/click/camref:1011ljPYw"
            )

        context["nocs"] = [
            code.code
            for code in operator_codes
            if code.source_name == "National Operator Codes"
        ]

        # vehicles tab:

        context["vehicles"] = self.object.vehicle_set.filter(
            withdrawn=False, latest_journey__isnull=False
        ).exists()
        if redis_client and (
            context["vehicles"] or any(s.tracking for s in context["services"])
        ):
            try:
                context["map"] = redis_client.exists(
                    f"operator{self.object.noc}vehicles"
                )
            except ConnectionError:
                pass

        return context

    def render_to_response(self, context):
        status_code = None

        if not context["services"] and not context["vehicles"]:
            alternative = Operator.objects.filter(
                operator_has_current_services,
                name=self.object.name,
            ).first()
            if alternative:
                return redirect(alternative)
            context["ad"] = False
            status_code = HTTPStatus.NOT_FOUND

        response = super().render_to_response(context)
        if status_code:
            response.status_code = status_code
        return response


class ServiceDetailView(DetailView):
    "A service and the stops it stops at"

    model = Service
    queryset = (
        model.objects.with_line_names()
        .select_related("region", "source", "colour")
        .prefetch_related("operator")
        .defer("search_vector")
    )

    def get_object(self, **kwargs):
        services = Service.objects

        try:
            service = super().get_object(**kwargs)
        except Http404 as e:
            slug = self.kwargs["slug"]

            service = services.filter(service_code=slug).first()

            if not service:
                service = services.filter(
                    servicecode__scheme="slug", servicecode__code=slug
                ).first()

            if not service:
                service = services.filter(
                    servicecode__scheme="ServiceCode", servicecode__code=slug
                ).first()

            if not service:
                raise e

        if not service.current:
            alternative = None

            services = services.only("slug", "current").filter(current=True)
            operators = service.operator.all()

            if service.line_name:
                if operators:
                    alternative = services.filter(
                        line_name__iexact=service.line_name,
                        operator__in=operators,
                        stops__service=service,
                    ).first()
                if not alternative:
                    alternative = services.filter(
                        line_name__iexact=service.line_name,
                        stops__service=service,
                    ).first()
                if not alternative and operators:
                    alternative = services.filter(
                        line_name__iexact=service.line_name,
                        operator__in=service.operator.all(),
                    ).first()

            if not alternative and service.description:
                alternative = services.filter(description=service.description).first()

            if not alternative and operators:
                alternative = operators[0]

            if alternative:
                return alternative

            raise Http404()

        return service

    def get_fare_tables(self):
        fare_tables = (
            FareTable.objects.filter(
                tariff__services=self.object,
                tariff__source__published=True,
            )
            .select_related("tariff", "user_profile", "sales_offer_package")
            .order_by("tariff")
        )
        if fare_tables:
            for table in fare_tables:
                table.tariff.name = (
                    table.tariff.name.removesuffix(" fares")
                    .replace(" Conc ", " Concession ")
                    .replace(" YP ", " Young Person ")
                    .replace(" Ch ", " Child ")
                    .replace("_", " ")
                    .replace(" AD ", " Adult ")
                )

            if not all(
                table.user_profile == fare_tables[0].user_profile
                for table in fare_tables[1:]
            ):
                for table in fare_tables:
                    table.tariff.name = f"{table.tariff.name} - {table.user_profile} {table.tariff.trip_type}"
            if not all(
                table.sales_offer_package == fare_tables[0].sales_offer_package
                for table in fare_tables[1:]
            ):
                for table in fare_tables:
                    table.tariff.name = (
                        f"{table.tariff.name} - {table.sales_offer_package}"
                    )

            if not all(
                table.tariff.name == fare_tables[0].tariff.name
                for table in fare_tables[1:]
            ):
                parts = fare_tables[0].tariff.name.split()
                while all(
                    table.tariff.name.startswith(f"{parts[0]} ")
                    for table in fare_tables
                ):
                    for table in fare_tables:
                        table.tariff.name = table.tariff.name.removeprefix(
                            f"{parts[0]} "
                        )
                    parts = parts[1:]
            return fare_tables

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if (
            type(self.object) is not self.model
            or self.object.slug != self.kwargs["slug"]
        ):
            return {"redirect_to": self.object}

        operators = self.object.operator.all()
        context["operators"] = operators

        context["related"] = self.object.get_similar_services()
        if context["related"]:
            context["colours"] = get_colours(
                [
                    service
                    for service in context["related"]
                    if service.colour_id != self.object.colour_id
                ]
            )

        # timetable

        date = None

        if not self.object.timetable_wrong:
            form = forms.TimetableForm(
                self.request.GET or None,
                service=self.object,
                related=context["related"],
            )

            context["timetable"] = form.get_timetable(self.object)

            context["form"] = form

            if form.is_valid():
                date = form.cleaned_data.get("date")

                # date in past - redirect to today?
                if (
                    date
                    and not (
                        context["timetable"].calendars
                        and context["timetable"].calendar_ids
                    )
                    and date < timezone.localdate()
                ):
                    return {"redirect_to": self.object}

            context["registrations"] = Registration.objects.filter(
                Exists(self.object.route_set.filter(registration=OuterRef("id")))
            )

        if self.object.tracking and self.object.vehiclejourney_set.exists():
            context["vehicles"] = True

        # disruptions

        consequences = Consequence.objects.filter(
            Q(services=self.object) | (Q(operators__in=operators, services=None))
        )
        context["situations"] = (
            Situation.objects.filter(
                Exists(consequences.filter(situation=OuterRef("id"))),
                publication_window__contains=Now(),
                current=True,
            )
            .prefetch_related(
                Prefetch(
                    "consequence_set",
                    queryset=consequences.prefetch_related("stops"),
                    to_attr="consequences",
                ),
                "link_set",
                "validityperiod_set",
            )
            .defer("data")
        )
        # stop_situations = {}
        # for situation in context["situations"]:
        #     for consequence in situation.consequences:
        #         for stop in consequence.stops.all():
        #             stop_situations[stop.atco_code] = situation

        context["stopusages"] = self.object.stopusage_set.select_related(
            "stop__locality"
        ).defer("stop__latlong", "stop__locality__latlong")
        context["has_minor_stops"] = SimpleLazyObject(
            lambda: any(stop_usage.is_minor() for stop_usage in context["stopusages"])
        )

        #     if len(stop_situations) < len(context["stopusages"]):
        #         for stop_usage in context["stopusages"]:
        #             if stop_usage.stop_id in stop_situations:
        #                 if (
        #                     stop_situations[stop_usage.stop_id].summary
        #                     == "Does not stop here"
        #                 ):
        #                     stop_usage.suspended = True
        #                 else:
        #                     stop_usage.situation = True

        try:
            context["breadcrumb"] = [
                Region.objects.filter(adminarea__stoppoint__service=self.object)
                .distinct()
                .get()
            ]
        except (Region.DoesNotExist, Region.MultipleObjectsReturned):
            context["breadcrumb"] = [self.object.region]

        context["links"] = []

        if operators:
            operator = operators[0]
            context["breadcrumb"].append(operator)
            context["payment_methods"] = []

            if operator.operatorcode_set.filter(source__name="MyTrip").exists():
                context["app"] = {
                    "url": reverse("operator_tickets", kwargs={"slug": operator.slug}),
                    "name": "MyTrip app",
                }
            for method in PaymentMethod.objects.filter(
                Exists(
                    Service.payment_methods.through.objects.filter(
                        payment_method=OuterRef("id"),
                        service=self.object,
                        accepted=True,
                    )
                )
                | Exists(
                    Operator.payment_methods.through.objects.filter(
                        paymentmethod=OuterRef("id"),
                        operator=operator,
                    )
                ),
                ~Exists(
                    Service.payment_methods.through.objects.filter(
                        payment_method=OuterRef("id"),
                        service=self.object,
                        accepted=False,
                    )
                ),
            ):
                if "app" in method.name and method.url:
                    context["app"] = method
                else:
                    context["payment_methods"].append(method)
            for operator in operators:
                if operator.name == "National Express":
                    context["tickets_link"] = (
                        "https://nationalexpress.prf.hn/click/camref:1011ljPYw"
                    )
                    context["links"].append(
                        {
                            "url": context["tickets_link"],
                            "text": "Buy tickets at National Express",
                        }
                    )
                    break

        context["fare_tables"] = self.get_fare_tables()

        for url, text in self.object.get_traveline_links(date):
            context["links"].append({"url": url, "text": text})

        return context

    def render_to_response(self, context):
        if "redirect_to" in context:
            return redirect(
                context["redirect_to"],
                permanent=(type(context["redirect_to"]) is self.model),
            )

        if not settings.TEST:
            template = get_template("busstops/service_detail.html")
            generator = template.template.generate(
                **context, ad=True, request=self.request
            )
            return StreamingHttpResponse(
                generator,
                content_type="text/html",
                headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
            )

        return super().render_to_response(context)


def service_timetable(request, service_id):
    services = Service.objects.with_line_names().defer("geometry", "search_vector")
    service = get_object_or_404(services, id=service_id)
    related_options = service.get_similar_services()
    form = forms.TimetableForm(request.GET, service=service, related=related_options)

    context = {
        "object": service,
        "timetable": form.get_timetable(service),
        "related": related_options,
        "form": form,
    }

    return render(request, "timetable.html", context)


def service_timetable_csv(request, service_id):
    services = Service.objects.with_line_names().defer("geometry", "search_vector")
    service = get_object_or_404(services, id=service_id)
    form = forms.TimetableForm(request.GET, service=service, related=None)

    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={service.slug}.csv"},
    )
    writer = csv.writer(response)

    for grouping in form.get_timetable(service).render().groupings:
        writer.writerow(
            ["stop", "NaPTAN code", "ATCO code"]
            + [trip.route.line_name for trip in grouping.trips]
        )
        for row in grouping.rows:
            if type(row.stop) is StopPoint:
                stop = [
                    row.stop.get_qualified_name(),
                    row.stop.naptan_code,
                    row.stop.atco_code,
                ]
            else:
                stop = [
                    str(row.stop),
                    "",
                    "",
                ]
            writer.writerow(stop + row.times)
        writer.writerow(())
    return response


@cdn_cache_control(max_age=7200)
def service_map_data(request, service_id):
    service = get_object_or_404(
        Service.objects.only("geometry", "line_name", "service_code"),
        id=service_id,
    )
    stops = service.stops.filter(
        ~Exists(
            Situation.objects.filter(
                summary="Does not stop here",
                consequence__stops=OuterRef("pk"),
                consequence__services=service,
            )
        ),
        latlong__isnull=False,
    )
    stops = stops.distinct().order_by().select_related("locality").in_bulk()
    data = {
        "stops": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": stop.latlong.coords,
                    },
                    "properties": {
                        "name": stop.get_qualified_name(),
                        "indicator": stop.indicator,
                        "bearing": stop.get_heading(),
                        "url": stop.get_absolute_url(),
                    },
                }
                for stop in stops.values()
            ],
        },
        "geometry": {"type": "MultiLineString", "coordinates": []},
    }

    trips = (
        Trip.objects.only("id")
        .annotate(
            stop_ids=ArraySubquery(
                StopTime.objects.filter(trip=OuterRef("id")).values("stop")
            ),
        )
        .filter(route__service=service)
    )

    route_links = {
        (route_link.from_stop_id, route_link.to_stop_id): route_link
        for route_link in service.routelink_set.all()
    }

    if not route_links and type(service.geometry) is MultiLineString:
        multi_line_string = service.geometry.coords
    else:
        # build pairs of consecutive stops

        pairs = set()

        for trip in trips:
            previous_stop_id = None
            for stop_id in trip.stop_ids:
                if previous_stop_id:
                    pair = (previous_stop_id, stop_id)
                    if pair not in pairs:
                        pairs.add(pair)

                previous_stop_id = stop_id

        line_string = []
        multi_line_string = [line_string]

        previous_pair = None

        for pair in pairs:
            line_string = []
            multi_line_string.append(line_string)

            origin, destination = pair
            if previous_pair and line_string and previous_pair[1] != origin:
                line_string = []
                multi_line_string.append(line_string)
            if pair in route_links:
                line_string += route_links[pair].geometry.coords
            elif origin in stops and destination in stops:
                origin = stops[origin]
                destination = stops[destination]
                if origin.latlong and destination.latlong:
                    line_string += [
                        origin.latlong.coords,
                        destination.latlong.coords,
                    ]

            previous_pair = pair

    data["geometry"]["coordinates"] = multi_line_string

    return JsonResponse(data)


class OperatorSitemap(Sitemap):
    protocol = "https"

    def items(self):
        return (
            Operator.objects.filter(operator_has_current_services_or_vehicles)
            .annotate(
                lastmod=Coalesce(
                    SubqueryMax("service__modified_at", filter=Q(current=True)),
                    "modified_at",
                )
            )
            .only("slug")
            .order_by("noc")
        )

    def lastmod(self, obj):
        return obj.lastmod


class ServiceSitemap(Sitemap):
    protocol = "https"

    def items(self):
        return Service.objects.filter(current=True).only("slug", "modified_at")

    def lastmod(self, obj):
        return obj.modified_at


@cdn_cache_control(max_age=300)
def search(request):
    form = forms.SearchForm(request.GET)

    context = {
        "form": form,
    }

    if form.is_valid():
        query_text = form.cleaned_data["q"]
        context["query"] = query_text

        postcode = "".join(query_text.split()).upper()
        if validation.is_valid_postcode(postcode):
            res = requests.get(
                "https://api.postcodes.io/postcodes/" + postcode, timeout=1
            )
        elif validation.is_valid_partial_postcode(postcode):
            res = requests.get(
                "https://api.postcodes.io/outcodes/" + postcode, timeout=1
            )
        else:
            postcode = None

        if postcode and res.ok:
            result = res.json()["result"]

            if result["longitude"] is not None:
                point = Point(result["longitude"], result["latitude"], srid=4326)

                context["postcode"] = {
                    "postcode": result.get("postcode") or result.get("outcode"),
                    "latlong": point,
                    "localities": (
                        Locality.objects.filter(latlong__bboverlaps=point.buffer(0.05))
                        .filter(
                            Q(stoppoint__active=True)
                            | Q(locality__stoppoint__active=True)
                        )
                        .distinct()
                        .annotate(distance=Distance("latlong", point))
                        .order_by("distance")
                        .defer("latlong")[:20]
                    ),
                }

        if "postcode" not in context or not result.get("postcode"):
            query = SearchQuery(query_text, search_type="websearch", config="english")
            rank = SearchRank(F("search_vector"), query)

            localities = Locality.objects.filter(
                Exists("stoppoint") | Exists("locality")
            )
            operators = Operator.objects.filter(
                operator_has_current_services_or_vehicles
            )
            services = Service.objects.with_line_names().filter(current=True)

            services = services.annotate(
                operators=ArrayAgg("operator__name", distinct=True, default=None)
            )

            for key, queryset in (
                ("localities", localities),
                ("operators", operators),
                ("services", services),
            ):
                if key == "services" and len(query_text) <= 3:
                    queryset = queryset.filter(
                        Q(search_vector=query) | Q(line_name__iexact=query_text)
                    )
                else:
                    queryset = queryset.filter(search_vector=query)

                queryset = queryset.annotate(rank=rank).order_by("-rank")

                if key == "operators" or key == "localities":
                    queryset = queryset.annotate(headline=SearchHeadline("name", query))
                elif key == "services":
                    queryset = queryset.annotate(
                        headline=SearchHeadline("description", query)
                    )
                context[key] = Paginator(queryset, 20).get_page(request.GET.get("page"))

            vehicles = Vehicle.objects.select_related("operator")
            query_text = query_text.replace(" ", "")
            if len(query_text) >= 4:
                if query_text.isdigit():
                    context["vehicles"] = vehicles.filter(fleet_code__iexact=query_text)
                elif not query_text.isalpha():
                    context["vehicles"] = vehicles.filter(
                        Q(reg__iexact=query_text)
                        | Q(**{"data__Previous reg__icontains": query_text})
                    )

            if context.get("services"):
                context["colours"] = get_colours(context["services"])

    return render(request, "search.html", context)


def journey(request):
    origin = request.GET.get("from")
    from_q = request.GET.get("from_q")
    destination = request.GET.get("to")
    to_q = request.GET.get("to_q")

    if origin:
        origin = get_object_or_404(Locality, slug=origin)
    if from_q:
        query = SearchQuery(from_q)
        rank = SearchRank(F("search_vector"), query)
        from_options = (
            Locality.objects.filter(search_vector=query)
            .annotate(rank=rank)
            .order_by("-rank")
        )
        if len(from_options) == 1:
            origin = from_options[0]
            from_options = None
        elif origin not in from_options:
            origin = None
    else:
        from_options = None

    if destination:
        destination = get_object_or_404(Locality, slug=destination)
    if to_q:
        query = SearchQuery(to_q)
        rank = SearchRank(F("search_vector"), query)
        to_options = (
            Locality.objects.filter(search_vector=query)
            .annotate(rank=rank)
            .order_by("-rank")
        )
        if len(to_options) == 1:
            destination = to_options[0]
            to_options = None
        elif destination not in to_options:
            destination = None
    else:
        to_options = None

    journeys = None
    # if origin and destination:
    #     journeys = Journey.objects.filter(
    #         stopusageusage__stop__locality=origin
    #     ).filter(stopusageusage__stop__locality=destination)
    # else:
    #     journeys = None

    return render(
        request,
        "journey.html",
        {
            "from": origin,
            "from_q": from_q or origin or "",
            "from_options": from_options,
            "to": destination,
            "to_q": to_q or destination or "",
            "to_options": to_options,
            "journeys": journeys,
        },
    )
