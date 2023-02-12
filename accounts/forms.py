from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.forms import EmailField, EmailInput, Form, NullBooleanField

UserModel = get_user_model()


class RegistrationForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].label = "Email address"
        self.fields["email"].help_text = "Will be kept private"

    def save(self, request=None):
        try:
            self.user = UserModel.objects.get(email__iexact=self.cleaned_data["email"])
        except UserModel.DoesNotExist:
            self.user = UserModel.objects.create_user(
                self.cleaned_data["email"], self.cleaned_data["email"]
            )

        if request and (ip_address := request.headers.get("do-connecting-ip")):
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


class AdminUserForm(Form):
    trusted = NullBooleanField()
