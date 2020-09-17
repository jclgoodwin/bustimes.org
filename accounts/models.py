from django.db.models.fields import EmailField
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    email = EmailField(unique=True, verbose_name='email address')

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'
