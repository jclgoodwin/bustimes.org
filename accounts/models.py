from django.db.models.fields import EmailField, BooleanField
from django.contrib.auth.models import AbstractUser
from django.urls import reverse


class User(AbstractUser):
    email = EmailField(unique=True, verbose_name='email address')
    trusted = BooleanField(null=True)

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'

    def get_absolute_url(self):
        return reverse('user_detail', args=(self.id,))

    def __str__(self):
        if self.is_staff:
            return self.username
        return f'{self.id}'
