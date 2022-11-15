from akismet import Akismet
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError


class ContactForm(forms.Form):
    name = forms.CharField(label="Name")
    email = forms.EmailField(label="Email address")
    message = forms.CharField(label="Message", widget=forms.Textarea)
    referrer = forms.CharField(
        label="Referrer", required=False, widget=forms.HiddenInput
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        if self.request and self.is_valid():
            message = self.cleaned_data["message"]

            if settings.AKISMET_API_KEY:
                akismet = Akismet(
                    api_key=settings.AKISMET_API_KEY,
                    blog=settings.AKISMET_SITE_URL,
                )

                is_spam = akismet.check(
                    user_ip=self.request.headers.get("do-connecting-ip"),
                    user_agent=self.request.headers.get("User-Agent"),
                    comment_type="contact-form",
                    comment_author=self.cleaned_data["name"],
                    comment_author_email=self.cleaned_data["email"],
                    comment_content=message,
                )

                if is_spam:
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
        if self.related:
            self.fields["service"].choices = [(s.id, s.line_name) for s in self.related]
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
