from django import forms
from turnstile.fields import TurnstileField


class ContactForm(forms.Form):
    name = forms.CharField(label="Name")
    email = forms.EmailField(label="Email address")
    message = forms.CharField(label="Message", widget=forms.Textarea)
    referrer = forms.CharField(
        label="Referrer", required=False, widget=forms.HiddenInput
    )
    turnstile = TurnstileField(label="Confirm that you’re a human (not a robot)")

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class SearchForm(forms.Form):
    q = forms.CharField(widget=forms.TextInput(attrs={"type": "search"}))


class TimetableForm(forms.Form):
    date = forms.DateField(required=False)
    calendar = forms.IntegerField(required=False)
    detailed = forms.BooleanField(required=False)
    vehicles = forms.BooleanField(required=False)
    service = forms.MultipleChoiceField(
        required=False, widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        self.related = kwargs.pop("related")
        super().__init__(*args, **kwargs)
        if self.related:
            self.fields["service"].choices = [
                (s.id, s.get_line_name()) for s in self.related
            ]
        else:
            del self.fields["service"]

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
            day=date,
            calendar_id=calendar_id,
            also_services=also_services,
            detailed=self.cleaned_data.get("detailed"),
        )


class DeparturesForm(forms.Form):
    date = forms.DateField()
    time = forms.TimeField(required=False)
