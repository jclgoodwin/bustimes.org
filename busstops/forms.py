# from antispam.honeypot.forms import HoneypotField
from antispam import akismet
from django import forms
from django.core.exceptions import ValidationError


class ContactForm(forms.Form):
    name = forms.CharField(label="Name")
    email = forms.EmailField(label="Email address")
    message = forms.CharField(label="Message", widget=forms.Textarea)
    # spam_honeypot_field = HoneypotField()
    referrer = forms.CharField(
        label="Referrer", required=False, widget=forms.HiddenInput
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        if (
            self.request
            and self.is_valid()
            and akismet.check(
                request=akismet.Request.from_django_request(self.request),
                comment=akismet.Comment(
                    content=self.cleaned_data["message"],
                    type="comment",
                    author=akismet.Author(
                        name=self.cleaned_data["name"], email=self.cleaned_data["email"]
                    ),
                ),
            )
        ):
            raise ValidationError("Spam detected", code="spam-protection")


class SearchForm(forms.Form):
    q = forms.CharField(widget=forms.TextInput(attrs={"type": "search"}))


class TimetableForm(forms.Form):
    date = forms.DateField(required=False)
    calendar = forms.IntegerField(required=False)
    detailed = forms.BooleanField(required=False)
    service = forms.MultipleChoiceField(
        required=False, widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        self.related = kwargs.pop("related")
        super().__init__(*args, **kwargs)
        self.fields["service"].choices = [(s.id, s.line_name) for s in self.related]

    def get_timetable(self, service):
        if self.is_valid():
            date = self.cleaned_data["date"]
            calendar_id = self.cleaned_data["calendar"]
            also_services = [
                s for s in self.related if str(s.id) in self.cleaned_data["service"]
            ]
        else:
            date = None
            calendar_id = None
            also_services = ()

        return service.get_timetable(
            day=date, calendar_id=calendar_id, also_services=also_services
        )


class DeparturesForm(forms.Form):
    date = forms.DateField()
    time = forms.TimeField(required=False)
