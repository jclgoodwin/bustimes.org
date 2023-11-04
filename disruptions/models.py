from django.contrib.postgres.fields import DateTimeRangeField
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import camel_case_to_spaces

from busstops.templatetags.date_range import date_range


class Situation(models.Model):
    source = models.ForeignKey(
        "busstops.DataSource",
        models.CASCADE,
        limit_choices_to={
            "name__in": (
                "bustimes.org",
                "TfL",
                "Bus Open Data",
                "Bus Open Data Service",
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
    publication_window = DateTimeRangeField()
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

    def list_validity_periods(self):
        validity_periods = self.validityperiod_set.all()
        if len(validity_periods) == 1:
            current_timezone = timezone.get_current_timezone()
            period = validity_periods[0].period
            if period.lower and period.upper:
                lower = period.lower.astimezone(current_timezone)
                upper = period.upper.astimezone(current_timezone)
                if lower.date() == upper.date():
                    return [
                        f"""{lower.strftime("%H:%M")}–{upper.strftime("%H:%M, %-d %B %Y")}"""
                    ]
            return [date_range(period)]


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
