from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import PermissionDenied
from django.forms import (
    BooleanField,
    CharField,
    EmailField,
    EmailInput,
    Form,
    NullBooleanField,
)

User = get_user_model()


class RegistrationForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].label = "Email address"
        self.fields["email"].help_text = "Will be kept private"

    def save(self, request=None):
        ip_address = request.headers.get("cf-connecting-ip")

        if ip_address:
            if User.objects.filter(trusted=False, ip_address=ip_address).exists():
                raise PermissionDenied

        try:
            self.user = User.objects.get(email__iexact=self.cleaned_data["email"])
        except User.DoesNotExist:
            self.user = User.objects.create_user(
                self.cleaned_data["email"], self.cleaned_data["email"]
            )

        if request and ip_address:
            self.user.ip_address = ip_address
            self.user.save(update_fields=["ip_address"])

        super().save(
            request=request,
            subject_template_name="registration/register_confirm_subject.txt",
            email_template_name="registration/register_confirm_email.txt",
            use_https=True,
        )

    def get_users(self, _):
        return [self.user]


class LoginForm(AuthenticationForm):
    username = EmailField(
        widget=EmailInput(attrs={"autofocus": True, "autocomplete": "email"})
    )


class UserForm(Form):
    name = CharField(
        required=False, label="Username", validators=[UnicodeUsernameValidator()]
    )
    trusted = NullBooleanField()


class DeleteForm(Form):
    confirm_delete = BooleanField(label="Please delete my account")
