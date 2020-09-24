from django.db.models.fields import EmailField
from django.contrib.auth.models import AbstractUser
from django.urls import reverse


class User(AbstractUser):
    email = EmailField(unique=True, verbose_name='email address')

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'

    def get_absolute_url(self):
        return reverse('user_detail', args=(self.id,))
