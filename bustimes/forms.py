import requests
from django.core.exceptions import ValidationError
from django.forms import (
    BooleanField,
    CharField,
    FileField,
    Form,
    HiddenInput,
    ModelChoiceField,
    formset_factory,
)

from busstops.models import Service

from . import snap


class UploadGTFSForm(Form):
    source_name = CharField(max_length=255)
    file = FileField(
        label="GTFS zip file", widget=FileField.widget(attrs={"accept": ".zip"})
    )
    note = CharField(
        max_length=255,
        required=False,
        help_text="A note that will be added to every trip",
    )


class SnapForm(Form):
    journey = CharField(label="Journey URL or ID")
    service = CharField(
        label="Local service slug or ID",
        required=False,
        help_text="Defaults to the journey's service's slug",
    )

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data
        try:
            journey = snap.get_journey(cleaned_data["journey"])
        except requests.RequestException as e:
            raise ValidationError(str(e))
        slug = cleaned_data["service"] or (journey["service"] or {}).get("slug", "")
        service = Service.objects.filter(
            **{"id" if slug.isdigit() else "slug": slug}
        ).first()
        if not service:
            raise ValidationError(f"No local service {slug}")
        cleaned_data["journey"] = journey
        cleaned_data["service"] = service
        return cleaned_data


class SaveRouteLinksForm(Form):
    service = ModelChoiceField(Service.objects, widget=HiddenInput)


class RouteLinkForm(Form):
    save = BooleanField(required=False)
    from_stop = CharField(widget=HiddenInput)
    to_stop = CharField(widget=HiddenInput)
    geometry = CharField(widget=HiddenInput)


RouteLinkFormSet = formset_factory(RouteLinkForm, extra=0)
