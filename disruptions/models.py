from django.contrib.postgres.fields import DateTimeRangeField
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import camel_case_to_spaces

from busstops.templatetags.date_range import date_range


def from_now():
    return [timezone.now()]


class Situation(models.Model):
    source = models.ForeignKey(
        "busstops.DataSource",
        models.CASCADE,
        limit_choices_to={
            "name__in": (
                "bustimes.org",
                "TfL",
                "Bus Open Data",
            )
        },
        default=236,
    )
    situation_number = models.CharField(max_length=36, blank=True)
    reason = models.CharField(max_length=25, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    participant_ref = models.CharField(max_length=36, blank=True)
    text = models.TextField(blank=True)
    data = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    publication_window = DateTimeRangeField(default=from_now)
    current = models.BooleanField(default=True)

    def __str__(self):
        return self.summary or self.text or super().__str__()

    def nice_reason(self):
        return camel_case_to_spaces(self.reason)

    def get_absolute_url(self):
        return reverse("situation", args=(self.id,))

    class Meta:
        indexes = [
            models.Index(fields=["current", "publication_window"]),
            models.Index(fields=["source", "situation_number"]),
        ]

    def list_validity_periods(self) -> list[str]:
        validity_periods = self.validityperiod_set.all()
        if not validity_periods:
            return []
        current_timezone = timezone.get_current_timezone()
        periods = [
            (
                period.period.lower
                and period.period.lower.astimezone(current_timezone),
                period.period.upper
                and period.period.upper.astimezone(current_timezone),
            )
            for period in validity_periods
        ]
        periods.sort()
        if len(periods) == 1:
            lower, upper = periods[0]
            if upper and lower and upper.date() == lower.date():
                return [
                    f"""{lower.strftime("%H:%M")}\u2009\u2013\u2009{upper.strftime("%H:%M, %-d %B %Y")}"""
                ]
            return [date_range(validity_periods[0].period)]
        elif len(validity_periods) > 1:
            first = periods[0]
            last = periods[-1]
            if (
                first[0]
                and last[0]
                and first[0].date() - last[0].date()
                == -timezone.timedelta(days=len(periods) - 1)
                and all(
                    period[0]
                    and period[1]
                    and first[0].time() == period[0].time()
                    and first[1].time() == period[1].time()
                    for period in periods[1:]
                )
            ):
                return [
                    f"""{first[0].strftime("%H:%M")}\u2009\u2013\u2009{first[1].strftime("%H:%M")},
{date_range(lower=first[0], upper=last[1])}"""
                ]
        return []


class Link(models.Model):
    url = models.URLField()
    situation = models.ForeignKey(Situation, models.CASCADE)

    def __str__(self):
        return self.url

    get_absolute_url = __str__


class ValidityPeriod(models.Model):
    situation = models.ForeignKey(Situation, models.CASCADE)
    period = DateTimeRangeField()

    def __str__(self):
        return date_range(self.period)


class Consequence(models.Model):
    situation = models.ForeignKey(Situation, models.CASCADE)
    stops = models.ManyToManyField("busstops.StopPoint", blank=True)
    services = models.ManyToManyField("busstops.Service", blank=True)
    operators = models.ManyToManyField("busstops.Operator", blank=True)
    text = models.TextField(blank=True)
    data = models.TextField(blank=True)

    def __str__(self):
        return self.text

    def get_absolute_url(self):
        service = self.services.first()
        if service:
            return service.get_absolute_url()
        return ""
