from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm

UserModel = get_user_model()


class RegistrationForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['email'].label = 'Email address'
        self.fields['email'].help_text = 'Will be kept private'

    def save(self, request=None):
        try:
            self.user = UserModel.objects.get(email__iexact=self.cleaned_data['email'])
        except UserModel.DoesNotExist:
            self.user = UserModel.objects.create_user(
                self.cleaned_data['email'],
                self.cleaned_data['email']
            )

        super().save(
            request=request,
            subject_template_name='registration/register_confirm_subject.txt',
            email_template_name='registration/register_confirm_email.txt',
            use_https=True
        )

    def get_users(self, _):
        return [self.user]
